#!/usr/bin/env python3
"""
Core specification generator for Tech-SpecGen.
"""

import os
import json
import shutil
import time
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

from src.services.agents_catalogue.genspec.src.services.client_factory import get_client_class
from src.services.agents_catalogue.genspec.src.services.db_cost_calculator import DatabaseCostCalculator
from src.services.agents_catalogue.genspec.src.services.prd_analyzer import PRDAnalyzer
from src.services.agents_catalogue.genspec.src.context import ServiceContextManager
from src.providers.logger import Logger
from src.api.dependencies import get_logger


class SpecGenerator:
    """
    Core specification generator.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the specification generator.
        
        Args:
            config: Configuration dictionary
        """
        self.logger = get_logger("spec-generator")
        self.config = config
        # Load template paths
        self.template_base_path = config.get("templates", {}).get("base_path", "src/services/agents_catalogue/genspec/src/prompts_for_sections/sections")

        ClientClass = get_client_class(config["provider"])
        self.bedrock_client = ClientClass(config)
        self.template_sections = config.get("templates", {}).get("sections", [])
        
        # Set up architecture images directory
        self.architecture_images_dir = config.get("paths", {}).get("architecture_images", "assets/architecture_images")
        self.prompt_templates = {}
        os.makedirs(self.architecture_images_dir, exist_ok=True)
        
        # Initialize service context manager
        self.service_context_manager = ServiceContextManager(config)
        
        self.logger.info(f"Initialized SpecGenerator with {len(self.template_sections)} template sections")
    
    def generate_spec(self, project_name: str, problem_statement: str, parsed_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate a complete technical specification.
        
        Args:
            project_name: Name of the project
            problem_statement: Problem statement text
            parsed_data: Dictionary of parsed input data
            
        Returns:
            Complete specification data
        """
        self.logger.info(f"Generating specification for project: {project_name}")
        
        # Process architecture images if present
        if "architecture" in parsed_data and parsed_data["architecture"].get("type") == "image":
            parsed_data["architecture"] = self._process_architecture_image(parsed_data["architecture"])
        
        # Prepare the specification structure
        spec_data = {
            "title": f"Technical Specification: {project_name}",
            "metadata": {
                "project_name": project_name,
                "generated_date": datetime.now().strftime("%Y-%m-%d"),
                "generator": "Tech-SpecGen"
            },
            "sections": []
        }
        
        # Generate each section
        for section_template in self.template_sections:
            section_data = self._generate_section(
                section_template, 
                project_name, 
                problem_statement, 
                parsed_data
            )
            
            if section_data:
                spec_data["sections"].append(section_data)
        
        self.logger.info(f"Generated specification with {len(spec_data['sections'])} sections")
        return spec_data
    
    def _process_architecture_image(self, architecture_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process an architecture image by copying it to the assets directory.
        
        Args:
            architecture_data: The parsed architecture image data
            
        Returns:
            Updated architecture data with new file path
        """
        original_path = architecture_data.get("content", "")
        if not original_path or not os.path.exists(original_path):
            return architecture_data
            
        # Copy the image to the assets directory
        file_name = architecture_data.get("file_name", os.path.basename(original_path))
        new_path = os.path.join(self.architecture_images_dir, file_name)
        
        try:
            shutil.copy2(original_path, new_path)
            self.logger.info(f"Copied architecture image from {original_path} to {new_path}")
            
            # Update the architecture data with the new path
            architecture_data["content"] = new_path
            architecture_data["original_path"] = original_path
            
            return architecture_data
        except Exception as e:
            self.logger.error(f"Error copying architecture image: {str(e)}")
            return architecture_data
    
    def _generate_section(self, template_file: str, project_name: str, 
                         problem_statement: str, parsed_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate a single section of the specification.
        
        Args:
            template_file: Filename of the section template
            project_name: Name of the project
            problem_statement: Problem statement text
            parsed_data: Dictionary of parsed input data
            
        Returns:
            Section data dictionary
        """
        # Extract section number and name from template filename
        section_parts = template_file.split('_', 1)
        if len(section_parts) < 2:
            section_number = ""
            section_name = template_file.replace('.txt', '')
        else:
            section_number = section_parts[0]
            section_name = section_parts[1].replace('.txt', '').replace('_', ' ').title()
        
        self.logger.info(f"Generating section: {section_name}")
        
        # Special handling for API documentation section
        if "api_documentation" in template_file and "api_documentation" in parsed_data:
            return self._generate_api_documentation_section(section_name, parsed_data)
        
        # Special handling for current architecture section
        if "current_architecture" in template_file and "architecture" in parsed_data:
            return self._generate_current_architecture_section(section_name, parsed_data["architecture"])
        
        # Special handling for evaluated approaches section
        if "evaluated_approaches" in template_file:
            return self._generate_evaluated_approaches_section(section_name, project_name, problem_statement, parsed_data)
        
        # Skip generating data model changes, business logic changes, and DB evaluation sections
        # as they're already included in the evaluated approaches section
        if "data_model_changes" in template_file or "business_logic_changes" in template_file or "db_evaluation" in template_file:
            self.logger.info(f"Skipping {section_name} as it's included in the evaluated approaches section")
            return None
        
        # Check if we need to generate missing data for sections that require it
        if ("goals" in template_file or "assumptions" in template_file or "scope" in template_file or 
            "out_of_scope" in template_file or "futuristic_scope" in template_file):
            # If key data is missing, derive it from the problem statement
            self._derive_missing_data(template_file, project_name, problem_statement, parsed_data)
        
        # Load template
        template_path = os.path.join(self.template_base_path, template_file)
        try:
            with open(template_path, 'r', encoding='utf-8') as f:
                template = f.read()
        except Exception as e:
            self.logger.error(f"Error loading template {template_file}: {str(e)}")
            return None
        
        # Prepare context for the prompt
        context = self._prepare_context(project_name, problem_statement, parsed_data)
        
        # Format the template with the context variables
        try:
            # Extract all variables from the template using regex
            import re
            variables = re.findall(r'\{([^{}]+)\}', template)
            
            # Create a dictionary with only the required variables
            template_vars = {}
            for var in variables:
                if var in context:
                    template_vars[var] = context[var]
                else:
                    self.logger.warning(f"Missing variable in template: {var}")
                    template_vars[var] = ""  # Provide empty string for missing variables
            
            # Format the template with the variables
            formatted_template = template.format(**template_vars)
            
            if section_name == "Nfr":
                nfrlist = parsed_data.get("nfrlist")
                if not nfrlist:
                    formatted_template = "No NFRs required to evaluate"
                else:
                    formatted_template = get_custom_nfr_prompt(formatted_template, nfrlist)
                    formatted_template = get_custom_nfr_prompt(formatted_template, parsed_data["nfrlist"])

            # Set a longer timeout for problem statement section
            timeout = 180 if "problem_statement" in template_file else 60
            self.logger.info(f"Using timeout of {timeout}s for {section_name}")
            
            # Generate content using Bedrock
            try:
                content = self.bedrock_client.generate_text(
                    formatted_template,
                    timeout=timeout
                )
                
                # Create section data
                section_data = {
                    "title": f"{section_name}",
                    "content": content
                }
                
                return section_data
            except Exception as e:
                error_msg = f"Error generating section {section_name}: {str(e)}"
                self.logger.error(error_msg)
                return {
                    "title": f"{section_name}",
                    "content": f"⚠️ Error generating content: {str(e)}\n\nPlease try regenerating this section."
                }
        except Exception as e:
            error_msg = f"Error formatting template for {section_name}: {str(e)}"
            self.logger.error(error_msg)
            return {
                "title": f"{section_name}",
                "content": f"⚠️ Error formatting template: {str(e)}\n\nPlease check the template variables."
            }
    
    def _generate_api_documentation_section(self, section_name: str, parsed_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate API documentation section based on problem statement and architecture.
        
        Args:
            section_name: Name of the section
            parsed_data: Dictionary of parsed input data
            
        Returns:
            Dictionary containing the generated section data
        """
        # Check if no API documentation is needed
        if parsed_data.get("api_documentation", {}).get("type") == "none":
            self.logger.info("No API documentation needed as per user input.")
            return {
                "title": section_name,
                "content": "No API documentation required."
            }
        

        # Check if API documentation is user-provided
        if parsed_data.get("api_documentation", {}).get("type") == "user_provided":
            self.logger.info("Using user-provided API documentation.")
            user_content = parsed_data["api_documentation"]["content"]
            
            # Enhance the user-provided content with formatting
            prompt = f"""
                Enhance the following API documentation to ensure it is clear and professional. Focus on improving the structure and clarity of the documentation while preserving the provided cURL examples. Do not modify the cURL examples.

                API Documentation:
                {user_content}

                Enhancements Required:
                1. **Format**: Ensure the documentation is well-structured with clear headings and sections.
                2. **Clarity**: Use clear and concise language to describe each endpoint, its purpose, and how it should be used.
                3. **Consistency**: Ensure consistent use of terminology and formatting throughout the document.
                4. **Examples**: Include example request and response bodies where applicable, but do not alter the provided cURL examples.

                Output the enhanced API documentation with the above enhancements applied, ensuring that the cURL examples remain unchanged.
            """
     
        else: 
            self.logger.info("Auto-generating API documentation")
            
            # Prepare context for API generation
            context = self._prepare_context(
                parsed_data.get("project_name", ""),
                parsed_data.get("problem_statement", ""),
                parsed_data
            )
            
            # Create prompt for API documentation generation
            prompt = f"""
                Generate comprehensive API documentation for the "{context['project_name']}" system.

                CONTEXT:
                Problem Statement: {context['problem_statement']}
                Current Architecture: {context.get('current_architecture_description', 'Not specified')}

                REQUIREMENTS:
                Based on the problem statement and architecture, generate API documentation with:

                1. **API Overview** - Brief description of the API purpose and design principles (based on the problem statement)
                2. **Authentication** - How API authentication works for this specific system
                3. **Endpoints** - Complete list of API endpoints relevant to the problem statement with:
                - HTTP Method and Path
                - Headers required
                - Query Parameters (if any)
                - Request Body (for POST/PUT only, not for GET)
                - Response Body with example
                - Status codes

                FORMAT REQUIREMENTS:
                - Use proper HTTP methods (GET, POST, PUT, DELETE)
                - Create realistic endpoint paths based on the problem domain
                - Show proper JSON request/response formats relevant to the business domain
                - Include authentication headers appropriate for the system
                - Add proper status codes (200, 400, 401, 404, 500)
                - Make endpoints specific to the problem domain described in the problem statement

                IMPORTANT: Do NOT use generic examples. Base all API endpoints, request/response formats, and functionality on the specific problem statement and business domain provided above.

                Generate professional API documentation that would be suitable for developers to implement and integrate with this specific system.
                """
        
        try:
            # Generate API documentation content
            content = self.bedrock_client.generate_text(prompt, timeout=120)
            
            return {
                "title": section_name,
                "content": content
            }
        except Exception as e:
            self.logger.error(f"Error auto-generating API documentation: {str(e)}")
            return {
                "title": section_name,
                "content": f"⚠️ Error auto-generating API documentation: {str(e)}\n\nAPI documentation will be provided based on the technical implementation."
            }
    
    def _derive_missing_data(self, template_file: str, project_name: str, 
                           problem_statement: str, parsed_data: Dict[str, Any]) -> None:
        """
        Derive missing data for sections that require it.
        
        Args:
            template_file: Filename of the section template
            project_name: Name of the project
            problem_statement: Problem statement text
            parsed_data: Dictionary of parsed input data
        """
        # Check which data needs to be derived
        if "goals" in template_file and not parsed_data.get("goals") and not parsed_data.get("non_goals"):
            self.logger.info("Deriving goals and non-goals from problem statement")
            
            # Create a prompt to derive goals and non-goals
            prompt = f"""
Based on this problem statement for the project '{project_name}', extract:
1. The main goals of the project (what it aims to achieve)
2. The non-goals (what is explicitly out of scope)

Problem Statement:
{problem_statement}

Business Context:
{parsed_data.get('business_context', '')}

Current Challenges:
{parsed_data.get('current_challenges', '')}

Format your response as JSON with two fields: "goals" and "non_goals", both containing arrays of strings.
"""
            
            try:
                # Generate and parse the response
                response = self.bedrock_client.generate_text(prompt, timeout=60)
                
                # Try to parse as JSON
                import json
                import re
                
                # Look for JSON structure in the response
                json_match = re.search(r'\{[\s\S]*\}', response)
                if json_match:
                    try:
                        data = json.loads(json_match.group(0))
                        if "goals" in data:
                            parsed_data["goals"] = "\n".join([f"- {goal}" for goal in data["goals"]])
                        if "non_goals" in data:
                            parsed_data["non_goals"] = "\n".join([f"- {non_goal}" for non_goal in data["non_goals"]])
                    except:
                        self.logger.warning("Failed to parse goals/non-goals as JSON")
            except Exception as e:
                self.logger.error(f"Error deriving goals and non-goals: {str(e)}")
        
        if "assumptions" in template_file and not parsed_data.get("assumptions"):
            self.logger.info("Deriving assumptions from problem statement")
            
            # Create a prompt to derive assumptions
            prompt = f"""
Based on this problem statement for the project '{project_name}', extract:
1. Key technical and business assumptions that underpin this project

Problem Statement:
{problem_statement}

Business Context:
{parsed_data.get('business_context', '')}

Current Challenges:
{parsed_data.get('current_challenges', '')}

Format your response as JSON with an "assumptions" field containing an array of strings.
"""
            
            try:
                # Generate and parse the response
                response = self.bedrock_client.generate_text(prompt, timeout=60)
                
                # Try to parse as JSON
                import json
                import re
                
                # Look for JSON structure in the response
                json_match = re.search(r'\{[\s\S]*\}', response)
                if json_match:
                    try:
                        data = json.loads(json_match.group(0))
                        if "assumptions" in data:
                            parsed_data["assumptions"] = "\n".join([f"- {assumption}" for assumption in data["assumptions"]])
                    except:
                        self.logger.warning("Failed to parse assumptions as JSON")
            except Exception as e:
                self.logger.error(f"Error deriving assumptions: {str(e)}")
        
        if ("scope" in template_file or "out_of_scope" in template_file or "futuristic_scope" in template_file) and \
           not parsed_data.get("scope") and not parsed_data.get("out_of_scope") and not parsed_data.get("futuristic_scope"):
            self.logger.info("Deriving scope information from problem statement")
            
            # Create a prompt to derive scope information
            prompt = f"""
Based on this problem statement for the project '{project_name}', extract:
1. What is in scope for this project
2. What is explicitly out of scope
3. What might be considered for future scope

Problem Statement:
{problem_statement}

Business Context:
{parsed_data.get('business_context', '')}

Current Challenges:
{parsed_data.get('current_challenges', '')}

Format your response as JSON with three fields: "scope", "out_of_scope", and "futuristic_scope", each containing arrays of strings.
"""
            
            try:
                # Generate and parse the response
                response = self.bedrock_client.generate_text(prompt, timeout=60)
                
                # Try to parse as JSON
                import json
                import re
                
                # Look for JSON structure in the response
                json_match = re.search(r'\{[\s\S]*\}', response)
                if json_match:
                    try:
                        data = json.loads(json_match.group(0))
                        if "scope" in data:
                            parsed_data["scope"] = "\n".join([f"- {item}" for item in data["scope"]])
                        if "out_of_scope" in data:
                            parsed_data["out_of_scope"] = "\n".join([f"- {item}" for item in data["out_of_scope"]])
                        if "futuristic_scope" in data:
                            parsed_data["futuristic_scope"] = "\n".join([f"- {item}" for item in data["futuristic_scope"]])
                    except:
                        self.logger.warning("Failed to parse scope information as JSON")
            except Exception as e:
                self.logger.error(f"Error deriving scope information: {str(e)}")
    
    def _generate_current_architecture_section(self, section_name: str, architecture_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate the current architecture section, preserving the user's exact diagram.
        
        Args:
            section_name: Name of the section
            architecture_data: Parsed architecture data
            
        Returns:
            Section data dictionary
        """
        self.logger.info("Generating current architecture section with user's exact diagram")
        
        # Check if we're dealing with an image or a mermaid diagram
        if architecture_data.get("type") == "image":
            return self._generate_image_architecture_section(section_name, architecture_data)
        
        # Extract the original diagram content (for Mermaid diagrams or text)
        original_content = architecture_data.get("content", "")
        
        # NEW: Special handling for text architecture descriptions
        if architecture_data.get("type") == "text" or architecture_data.get("type") == "text_with_flowchart":
            return self._generate_text_architecture_section(section_name, architecture_data, original_content)
        
        # Existing handling for Mermaid diagrams
        # Create a prompt to generate explanatory text
        prompt = f"""
You are analyzing a system architecture diagram. Please provide a detailed explanation of this architecture.
Focus on:
1. The overall system structure
2. Key components and their responsibilities
3. How components interact with each other
4. Data flow through the system

Diagram:
{original_content}

Provide a comprehensive explanation that would help someone understand this architecture.
"""
        
        try:
            # Generate explanatory text
            explanation = self.bedrock_client.generate_text(prompt)
            
            # Combine the explanation with the original diagram
            content = f"""
## Current Architecture

{explanation}

### Architecture Diagram

```mermaid
{original_content.strip()}
```
"""
            
            return {
                "title": section_name,
                "content": content
            }
        except Exception as e:
            self.logger.error(f"Error generating current architecture section: {str(e)}")
            
            # Fallback to just showing the diagram
            content = f"""
## Current Architecture

```mermaid
{original_content.strip()}
```
"""
            
            return {
                "title": section_name,
                "content": content
            }

    def _generate_text_architecture_section(self, section_name: str, architecture_data: Dict[str, Any], original_content: str) -> Dict[str, Any]:
        """
        Generate architecture section from text description with generated flowchart.
        
        Args:
            section_name: Name of the section
            architecture_data: Parsed architecture data
            original_content: Original text description
            
        Returns:
            Section data dictionary
        """
        # Check if we already have pre-generated flowchart data (from CLI)
        if architecture_data.get("type") == "text_with_flowchart":
            self.logger.info("Using pre-generated flowchart from CLI")
            
            # Use the pre-generated data
            explanation = architecture_data.get("description", "Architecture analysis based on the provided text description.")
            mermaid_diagram = architecture_data.get("generated_flowchart", "")
            components = architecture_data.get("components", [])
            relationships = architecture_data.get("relationships", [])
            
            # Format components and relationships
            components_text = "\n".join(f"- {comp}" for comp in components) if components else "Components identified from the description above."
            relationships_text = "\n".join(f"- {rel}" for rel in relationships) if relationships else "Relationships identified from the description above."
            
        else:
            # Generate flowchart on-demand (original logic)
            self.logger.info("Generating flowchart from text architecture description")
            
            # Create a prompt to generate both explanation and flowchart
            prompt = f"""
You are analyzing a text description of a system architecture. Please:
1. Provide a detailed technical explanation of the architecture
2. Create a comprehensive Mermaid flowchart that visualizes the architecture
3. Identify key components and their relationships

Text Description:
{original_content}

Format your response as:

EXPLANATION:
(Detailed technical explanation)

MERMAID_DIAGRAM:
flowchart TD
    %% Use modern flowchart syntax with proper node shapes
    %% [Service] for services, (API) for APIs, [(Database)] for databases, ((External)) for external systems
    %% Include professional styling and clear labels
    %% Show actual data flows with descriptive arrow labels
    %% Use specific component names from the text description, not generic terms

COMPONENTS:
(List of key components)

RELATIONSHIPS:
(List of relationships and data flows)

CRITICAL REQUIREMENTS:
- Your Mermaid diagram MUST use 'flowchart TD' syntax (NOT 'graph TD')
- Use EXACT component names from the text description
- Include specific node shapes: [Service], (API), [(Database)], ((External))
- Show actual data flows with labeled arrows describing what data is transferred
- Apply professional styling with classDef and class assignments
- Use professional colors: blues #3498db #2980b9, greens #27ae60 #16a085, grays #95a5a6 #7f8c8d
- STRICTLY AVOID: red, pink, purple, orange, yellow, or any bright/neon colors
- Use only muted, professional colors suitable for business documentation
- Include error handling paths and retry mechanisms where mentioned
- Use consistent naming conventions throughout the diagram
"""
            
            try:
                # Generate analysis and flowchart
                analysis_result = self.bedrock_client.generate_text(prompt)
                
                # Parse the response
                explanation = ""
                mermaid_diagram = ""
                components = ""
                relationships = ""
                
                current_section = None
                for line in analysis_result.split('\n'):
                    line = line.strip()
                    
                    if line == "EXPLANATION:":
                        current_section = "explanation"
                        continue
                    elif line == "MERMAID_DIAGRAM:":
                        current_section = "mermaid"
                        continue
                    elif line == "COMPONENTS:":
                        current_section = "components"
                        continue
                    elif line == "RELATIONSHIPS:":
                        current_section = "relationships"
                        continue
                    
                    if current_section == "explanation" and line:
                        explanation += line + "\n"
                    elif current_section == "mermaid" and line:
                        mermaid_diagram += line + "\n"
                    elif current_section == "components" and line:
                        components += line + "\n"
                    elif current_section == "relationships" and line:
                        relationships += line + "\n"
                
                # Use the generated content
                components_text = components.strip() if components else "Components identified from the description above."
                relationships_text = relationships.strip() if relationships else "Relationships identified from the description above."
                
            except Exception as e:
                self.logger.error(f"Error generating text architecture section: {str(e)}")
                
                # Fallback to just showing the text description
                content = f"""
## Current Architecture

{original_content}
"""
                
                return {
                    "title": section_name,
                    "content": content
                }
        
        # Build the content (same for both pre-generated and on-demand)
        content = f"""
## Current Architecture

{explanation.strip()}

### Architecture Components
{components_text}

### Component Relationships
{relationships_text}

### Architecture Flowchart

```mermaid
{mermaid_diagram.strip()}
```

### Original Architecture Description
{original_content}
"""
        
        return {
            "title": section_name,
            "content": content
        }
    
    def _generate_image_architecture_section(self, section_name: str, architecture_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate the current architecture section with an image diagram.
        
        Args:
            section_name: Name of the section
            architecture_data: Parsed architecture data (image)
            
        Returns:
            Section data dictionary
        """
        self.logger.info("Generating current architecture section with image diagram")
        
        # Get image information
        file_content = architecture_data.get("content", "")
        file_path = architecture_data.get("file_name", "")
        file_name = architecture_data.get("file_name", "")
        image_type = architecture_data.get("image_type", "png")
        data_uri = architecture_data.get("content", "")
        
        # Try to generate a Mermaid diagram from the image using Claude Vision
        mermaid_diagram = ""
        architecture_description = ""
        try:
            self.logger.info("Attempting to analyze architecture image with Claude Vision")
            vision_result = self.bedrock_client.analyze_image_architecture(file_content, file_content)
            mermaid_diagram = vision_result.get("mermaid_diagram", "")
            architecture_description = vision_result.get("description", "")
        except Exception as e:
            self.logger.error(f"Error analyzing architecture image with Claude Vision: {str(e)}")
        
        # Create a prompt to generate explanatory text if we didn't get one from Vision
        if not architecture_description:
            prompt = f"""
You are analyzing a system architecture diagram from an image file named '{file_name}'.
The user has provided this architecture diagram to generate a technical specification.

Please provide a comprehensive technical explanation of the architecture shown in the diagram, including:
1. The overall system structure and design patterns used
2. Key components and their specific responsibilities
3. How data flows through the system
4. Integration points between components
5. Any notable technical constraints or considerations

This will serve as the foundation for understanding the current architecture in the technical specification.
"""
            
            try:
                # Generate explanatory text
                architecture_description = self.bedrock_client.generate_text(prompt)
            except Exception as e:
                self.logger.error(f"Error generating architecture description: {str(e)}")
                architecture_description = "No description available for the architecture diagram."
        
        try:
            # Extract architecture insights for evaluated approaches
            try:
                architecture_insights = self._extract_architecture_insights(file_name)
            except Exception as e:
                self.logger.error(f"Error extracting architecture insights: {str(e)}")
                architecture_insights = {}
            
            # Combine the explanation with the image reference and Mermaid diagram if available
            content = f"""
## Current Architecture

{architecture_description}

### Architecture Diagram

"""
            
            # Add the Mermaid diagram if we successfully generated one
            if mermaid_diagram:
                content += f"""
```mermaid
{mermaid_diagram}
```

### Original Architecture Diagram

![Architecture Diagram]({file_path})

"""
            else:
                # Just include the image if we couldn't generate a Mermaid diagram
                content += f"""
![Architecture Diagram]({file_path})

"""
            
            # Add the data URI for HTML formatters to use
            architecture_data_for_formatters = {
                "image_data_uri": data_uri,
                "image_file_path": file_path,
                "image_file_name": file_name,
                "image_type": image_type,
                "architecture_insights": architecture_insights,
                "mermaid_diagram": mermaid_diagram if mermaid_diagram else ""
            }
            
            return {
                "title": section_name,
                "content": content,
                "metadata": {
                    "architecture_image": architecture_data_for_formatters
                }
            }
        except Exception as e:
            self.logger.error(f"Error generating image architecture section: {str(e)}")
            
            # Fallback to just showing image reference
            content = f"""
## Current Architecture

![Architecture Diagram]({file_path})
"""
            
            return {
                "title": section_name,
                "content": content,
                "metadata": {
                    "architecture_image": {
                        "image_file_path": file_path
                    }
                }
            }
    
    def _extract_architecture_insights(self, image_name: str) -> Dict[str, Any]:
        """
        Extract insights from the architecture image name.
        
        Args:
            image_name: Name of the architecture image file
            
        Returns:
            Dictionary of architecture insights
        """
        # Create a prompt to extract insights from the image name
        prompt = f"""
Based on the architecture image filename '{image_name}', please identify:
1. Potential technology stack or components that might be used
2. Possible architecture patterns (microservices, monolith, serverless, etc.)
3. Likely system boundaries or integration points
4. Potential scalability or performance considerations

Provide your insights in JSON format with these categories.
"""
        
        try:
            # Generate insights
            insights_text = self.bedrock_client.generate_text(prompt)
            
            # Try to parse as JSON, fallback to text if parsing fails
            try:
                insights = json.loads(insights_text)
            except:
                insights = {
                    "raw_insights": insights_text
                }
                
            return insights
        except Exception as e:
            self.logger.error(f"Error extracting architecture insights: {str(e)}")
            return {
                "error": str(e),
                "filename": image_name
            }
    
    def _generate_evaluated_approaches_section(self, section_name: str, project_name: str, 
                                              problem_statement: str, parsed_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate the evaluated approaches section with multiple approaches and flowcharts.
        
        Args:
            section_name: Name of the section
            project_name: Name of the project
            problem_statement: Problem statement text
            parsed_data: Dictionary of parsed input data
            
        Returns:
            Section data dictionary
        """
        print("Generating evaluated approaches section with multiple approaches and flowcharts")
        
        # Get configuration for evaluated approaches
        timeout = 3600  # Default 1 hour
        break_into_chunks = True
        num_approaches = parsed_data['evaluated_approaches_count'] if 'evaluated_approaches_count' in parsed_data else 4

        # Force at least 4 approaches for better comparison
        num_approaches = min(4, num_approaches)

        self.logger.info(f"Using timeout: {timeout}s, break_into_chunks: {break_into_chunks}, num_approaches: {num_approaches}")
        
        # Prepare context
        context = self._prepare_context(project_name, problem_statement, parsed_data)
        
        # Extract architecture insights if available
        architecture_insights = {}
        mermaid_diagram = ""
        if "architecture" in parsed_data:
            arch_data = parsed_data["architecture"]
            if "metadata" in arch_data and "architecture_image" in arch_data["metadata"]:
                architecture_insights = arch_data["metadata"]["architecture_image"].get("architecture_insights", {})
                mermaid_diagram = arch_data["metadata"]["architecture_image"].get("mermaid_diagram", "")
            elif arch_data.get("type") == "image" and "metadata" in arch_data:
                architecture_insights = arch_data.get("metadata", {}).get("architecture_insights", {})
        
        # Extract domain-specific information from the problem statement
        domain_specific_prompt = f"""
Based on this problem statement, identify the specific domain, key technical components, and main challenges:

{problem_statement}

Return a JSON object with the following fields:
1. domain: The technical domain (e.g., payment processing, authentication, data analytics)
2. key_components: List of technical components likely involved
3. main_challenges: List of technical challenges to solve
4. technical_constraints: Any constraints mentioned or implied
5. integration_points: Systems that need to be integrated
"""
        
        try:
            # Get domain-specific insights with a timeout
            self.logger.info("Generating domain-specific insights")
            domain_insights_text = self.bedrock_client.generate_text(
                domain_specific_prompt,
                max_tokens=1024,  # Smaller token count for faster response
                timeout=60  # 60-second timeout
            )
            try:
                domain_insights = domain_insights_text
            except Exception as e:
                self.logger.warning(f"Failed to parse domain insights as JSON: {domain_insights_text}")
                self.logger.warning(f"Failed to parse domain insights as JSON: {str(e)}")
                # self.logger.warning("Failed to parse domain insights as JSON, using default values")
                domain_insights = {
                    "domain": "payment processing",
                    "key_components": ["payment service", "database"],
                    "main_challenges": ["ensuring data consistency"],
                    "technical_constraints": ["minimal downtime"],
                    "integration_points": ["existing payment system"]
                }
        except Exception as e:
            self.logger.error(f"Error generating domain insights: {str(e)}")
            domain_insights = {}
        
        # Add database-specific context if available
        database_context = ""
        if "database" in parsed_data and parsed_data["database"].get("type") != "none":
            db_data = parsed_data["database"]
            database_context = f"""
Database Information:
- Anticipated Changes: {db_data.get('anticipate_changes', 'Not specified')}
- Workload Type: {db_data.get('workload_type', 'Not specified')}
- ACID Requirements: {db_data.get('acid_requirements', 'Not specified')}
- Archival Policy: {db_data.get('archival_policy', 'Not specified')}
- International Support: {db_data.get('international_support', 'Not specified')}
- Highlight Failure Points: {db_data.get('highlight_failure_points', 'Not specified')}
- Idempotency Critical Areas: {db_data.get('idempotency_critical', 'Not specified')}
- Transaction Boundaries: {db_data.get('transaction_boundaries', 'Not specified')}
- Join Complexity: {db_data.get('join_complexity', 'Not specified')}
- Data Archival Policy: {db_data.get('data_archival', 'Not specified')}
- Transactions Importance: {db_data.get('transactions_importance', 'Not specified')}
- Schema Normalization: {db_data.get('normalization', 'Not specified')}
- Database Purpose: {db_data.get('database_purpose', 'Not specified')}
- Query Type: {db_data.get('query_type', 'Not specified')}
- Additional Details: {db_data.get('details', 'Not specified')}
"""
        
        # Add performance requirements if available
        performance_context = ""
        if "performance" in parsed_data:
            perf_data = parsed_data["performance"]
            performance_context = f"""
Performance Requirements:
- Latency: {perf_data.get('latency', 'Not specified')}
- Throughput: {perf_data.get('throughput', 'Not specified')}
- Availability: {perf_data.get('availability', 'Not specified')}
"""
        
        if not break_into_chunks:
            # Generate the entire section at once (original approach)
            return self._generate_full_approaches_section(
                section_name, 
                project_name, 
                problem_statement, 
                domain_insights, 
                database_context, 
                performance_context, 
                context, 
                mermaid_diagram, 
                architecture_insights,
                timeout,
                num_approaches
            )
        else:
            # Generate the section in chunks
            return self._generate_chunked_approaches_section(
                section_name, 
                project_name, 
                problem_statement, 
                domain_insights, 
                database_context, 
                performance_context, 
                context, 
                mermaid_diagram, 
                architecture_insights,
                parsed_data,
                timeout,
                num_approaches
            )
    
    def _wrap_mermaid_diagrams(self, content: str) -> str:
        """
        Post-process content to ensure all Mermaid diagrams are wrapped in code blocks.
        
        Args:
            content: Content string that may contain unwrapped Mermaid code
            
        Returns:
            Content with all Mermaid diagrams properly wrapped in code blocks
        """
        import re
        
        # Patterns to detect Mermaid diagrams
        mermaid_patterns = [
            r'(flowchart\s+(?:TD|LR|BT|RL))',
            r'(graph\s+(?:TD|LR|BT|RL))',
            r'(sequenceDiagram)',
            r'(classDiagram)',
            r'(stateDiagram-v2)',
            r'(erDiagram)',
            r'(gantt)',
            r'(pie)',
            r'(gitgraph)',
        ]
        
        # Split content into lines
        lines = content.split('\n')
        result_lines = []
        in_mermaid_block = False
        mermaid_lines = []
        
        i = 0
        while i < len(lines):
            line = lines[i]
            
            # Check if we're already in a mermaid code block
            if line.strip().startswith('```mermaid'):
                in_mermaid_block = True
                result_lines.append(line)
                i += 1
                continue
            
            # Check if we're ending a mermaid code block
            if in_mermaid_block and line.strip() == '```':
                result_lines.append(line)
                in_mermaid_block = False
                mermaid_lines = []
                i += 1
                continue
            
            # If we're inside a mermaid block, just add the line
            if in_mermaid_block:
                result_lines.append(line)
                i += 1
                continue
            
            # Check if this line starts a Mermaid diagram
            is_mermaid_start = False
            for pattern in mermaid_patterns:
                if re.search(pattern, line, re.IGNORECASE):
                    is_mermaid_start = True
                    break
            
            if is_mermaid_start:
                # Check if it's already wrapped (look backwards for ```mermaid)
                is_already_wrapped = False
                for k in range(max(0, i-3), i):
                    if k < len(lines) and lines[k].strip().startswith('```mermaid'):
                        is_already_wrapped = True
                        break
                
                if is_already_wrapped:
                    # Already wrapped, just add the line
                    result_lines.append(line)
                    i += 1
                    continue
                
                # Start collecting Mermaid lines
                result_lines.append('```mermaid')
                mermaid_lines = [line]
                
                # Look ahead to find where the diagram ends
                j = i + 1
                while j < len(lines):
                    next_line = lines[j]
                    
                    # Stop if we hit a blank line followed by non-indented content
                    if next_line.strip() == '':
                        # Check if next non-empty line starts a new section
                        k = j + 1
                        while k < len(lines) and lines[k].strip() == '':
                            k += 1
                        if k < len(lines):
                            next_non_empty = lines[k]
                            # If next line starts with #, -, *, or is a code block, we're done
                            if (next_non_empty.strip().startswith('#') or 
                                next_non_empty.strip().startswith('-') or
                                next_non_empty.strip().startswith('*') or
                                next_non_empty.strip().startswith('|') or
                                next_non_empty.strip().startswith('```')):
                                break
                    
                    # Stop if we hit another Mermaid diagram start
                    is_next_mermaid = False
                    for pattern in mermaid_patterns:
                        if re.search(pattern, next_line, re.IGNORECASE):
                            is_next_mermaid = True
                            break
                    if is_next_mermaid:
                        break
                    
                    mermaid_lines.append(next_line)
                    j += 1
                
                # Add all collected Mermaid lines
                result_lines.extend(mermaid_lines)
                result_lines.append('```')
                
                # Skip the lines we've already processed
                i = j
                mermaid_lines = []
            else:
                result_lines.append(line)
                i += 1
        
        return '\n'.join(result_lines)
    
    def _generate_full_approaches_section(self, section_name, project_name, problem_statement, 
                                         domain_insights, database_context, performance_context, 
                                         context, mermaid_diagram, architecture_insights,
                                         timeout=3600, num_approaches=4):
        """
        Generate the entire evaluated approaches section at once.
        """
        # Create a prompt to generate evaluated approaches
        
        # Prepare conditional parts separately to avoid nested f-strings (Python 3.9 compatibility)
        mermaid_section = ""
        if mermaid_diagram:
            mermaid_section = f"Current Architecture Diagram (Mermaid):\n```mermaid\n{mermaid_diagram}\n```"
        
        architecture_insights_section = ""
        if architecture_insights:
            architecture_insights_section = f"Architecture insights:\n{json.dumps(architecture_insights, indent=2)}"
        
        prompt = f"""
You are a senior technical architect evaluating implementation approaches for a technical specification (Section 7).

STRICTLY USE ONLY the following information to write a detailed, precise evaluation of implementation approaches.

Project Name: {project_name}
Problem Statement: {problem_statement}

Domain Information:
{json.dumps(domain_insights, indent=2)}

{database_context}
{performance_context}

Current Architecture:
{context.get("current_architecture_description", "No description available")}

{mermaid_section}

{architecture_insights_section}

Your evaluated approaches section MUST follow this exact structure and formatting:

### 7.1. Approaches Evaluation
Begin with a clear, concise introduction to the approaches being evaluated. Then identify the key technical challenges that need to be addressed.

For EACH approach (provide {num_approaches} approaches):

#### Approach [Number]: [Descriptive Name]
- Provide a comprehensive technical description of the approach architecture in a professional, concise tone
- Include a block diagram in Mermaid format illustrating the approach (MUST wrap in ```mermaid code blocks)
- Include a sequence diagram in Mermaid format showing the request flow (MUST wrap in ```mermaid code blocks)
- Detail the specific components, services, and technologies involved with exact names
- Explain the data flow and processing logic with step-by-step sequences
- Document the integration patterns and interfaces with specific API details

**Pros:**
- List all advantages in bullet points
- Be specific and technical
- Include performance, scalability, and reliability benefits

**Cons:**
- List all disadvantages in bullet points
- Be specific about limitations and challenges
- Include implementation complexity, cost implications, and timeline considerations

After describing all approaches, include a comparative analysis table showing how each approach performs against key evaluation criteria.

#### Final Approach
- Provide a detailed technical justification for the recommended approach
- Explain how it specifically addresses the requirements and constraints
- Reference the specific pros that led to its selection
- Address how the cons will be mitigated
- Include a more detailed architecture diagram of the selected approach

### 7.2. Data model/Schema Changes
- Detail all database schema changes required
- Explain any data migration or seeding requirements
- Document any changes to relationships between entities

IMPORTANT: Based on the database requirements provided, include a detailed database recommendation section with a comparative analysis of appropriate database options. Consider the following database options and their characteristics:

1. PostgreSQL / Aurora:
   - Joins: Native, relational
   - Aggregations: Good
   - Regex Filtering: Good (with indexes)
   - Real-time ingestion: Batching or manual
   - Read latency: Low
   - Scalability: Vertical or replicas
   - Data volume efficiency: Disk intensive
   - Mutation support: Good
   - Consistency: Strong
   - Monitoring & Tracing: AWS
   - Ease of setup: Easy
   - Cost: Moderate/High

2. Rockset:
   - Joins: Fast, supports joins
   - Aggregations: Real-time aggregations
   - Regex Filtering: Good
   - Real-time ingestion: Built-in CDC/Kafka
   - Read latency: Low
   - Scalability: Fully managed, elastic
   - Data volume efficiency: Columnar + compressed
   - Mutation support: Limited mutation
   - Consistency: Eventual
   - Monitoring & Tracing: In-built tracing
   - Ease of setup: Easy (SaaS)
   - Cost: Usage-based (can spike)

3. Elasticsearch:
   - Joins: Limited, not traditional joins
   - Aggregations: Supported but not primary use
   - Regex Filtering: Excellent
   - Real-time ingestion: Near real-time with Logstash
   - Read latency: Low
   - Scalability: Horizontal
   - Data volume efficiency: Large index size
   - Mutation support: No updates
   - Consistency: Eventual
   - Monitoring & Tracing: Kibana, slow logs
   - Ease of setup: Easy (implemented for other use cases)
   - Cost: Indexing can pose a cost concern

4. TiDB:
   - Joins: Full SQL Joins
   - Aggregations: Very good
   - Regex Filtering: Native MySQL Regex
   - Real-time ingestion: TiCDC + Kafka
   - Read latency: Low (Indexes + Caching)
   - Scalability: Auto Sharding + Scale out
   - Data volume efficiency: Efficient Partitioning
   - Mutation support: ACID + Mutations
   - Consistency: Strong Consistency (Raft)
   - Monitoring & Tracing: Prometheus
   - Ease of setup: Easy (already there in system)
   - Cost: Efficient

5. Apache Solr:
   - Similar to Elasticsearch but with different trade-offs

Recommend the most appropriate database solution based on the specific requirements provided.

### 7.3. Business Logic Changes
- Outline all changes to business logic components
- Detail any new algorithms or processing flows
- Explain configuration changes and their impact

IMPORTANT FORMATTING INSTRUCTIONS:
- Use proper markdown headings (### for section 7.1, 7.2, 7.3 and #### for subsections)
- ALWAYS wrap Mermaid diagrams in code blocks: ```mermaid\n<diagram code>\n```
- Use Mermaid diagram syntax for architecture diagrams, sequence diagrams, and flowcharts
- Use tables for presenting comparative analysis
- Use bullet points for pros/cons and other lists
- Maintain a professional, concise technical writing style throughout
- Use specific technical terminology appropriate to the domain
- Format the document exactly like the example provided
"""
        
        try:
            # Generate evaluated approaches content with a timeout
            self.logger.info("Generating evaluated approaches content")
            
            # Add retry logic for transient errors
            max_retries = 3
            retry_delay = 1  # seconds
            
            for attempt in range(max_retries):
                try:
                    content = self.bedrock_client.generate_text(
                        prompt,
                        max_tokens=4096,  # Full token count for comprehensive response
                        timeout=3600  # 60-minute timeout
                    )
                    
                    # Post-process content to ensure Mermaid diagrams are wrapped in code blocks
                    content = self._wrap_mermaid_diagrams(content)
                    
                    self.logger.info("Successfully generated evaluated approaches content")
                    return {
                        "title": section_name,
                        "content": content
                    }
                except Exception as e:
                    if attempt < max_retries - 1:
                        self.logger.warning(f"Error on attempt {attempt + 1}/{max_retries}: {str(e)}. Retrying in {retry_delay} seconds...")
                        time.sleep(retry_delay)
                        retry_delay *= 2  # Exponential backoff
                    else:
                        self.logger.error(f"Failed after {max_retries} attempts: {str(e)}")
                        raise RuntimeError(f"Failed to generate evaluated approaches content: {str(e)}")
            
        except Exception as e:
            self.logger.error(f"Error generating evaluated approaches section: {str(e)}")
            raise RuntimeError(f"Failed to generate evaluated approaches section: {str(e)}")
    
    def _generate_db_evaluation_section(self, project_name: str, problem_statement: str, 
                                 parsed_data: Dict[str, Any], timeout: int = 300) -> str:
        """
        Generate a dedicated database evaluation section.
        
        Args:
            project_name: Name of the project
            problem_statement: Problem statement text
            parsed_data: Dictionary of parsed input data
            timeout: Timeout in seconds for generation
            
        Returns:
            Generated database evaluation content
        """
        self.logger.info("Generating database evaluation section")
        
        # Check if database context exists
        if parsed_data.get("database").get("type") == "none":
            self.logger.info("No database context found, skipping DB evaluation section")
            return ""
        
        # Load the DB evaluation template
        try:
            with open(os.path.join(self.template_base_path, "7_4_db_evaluation.txt"), 'r', encoding='utf-8') as f:
                template = f.read()
        except Exception as e:
            self.logger.error(f"Error loading DB evaluation template: {str(e)}")
            return "### 7.4. Database Evaluation\n\n*Error loading database evaluation template*"
        
        # Prepare context for the prompt
        context = self._prepare_context(project_name, problem_statement, parsed_data)
        
        # Format the template with the context variables
        try:
            # Extract all variables from the template using regex
            import re
            variables = re.findall(r'\{([^{}]+)\}', template)
            
            # Create a dictionary with only the required variables
            template_vars = {}
            for var in variables:
                if var in context:
                    template_vars[var] = context[var]
                else:
                    self.logger.warning(f"Missing variable in DB evaluation template: {var}")
                    template_vars[var] = ""  # Provide empty string for missing variables
            
            # Format the template with the variables
            formatted_template = template.format(**template_vars)
            
            # Generate content using Bedrock
            try:
                content = self.bedrock_client.generate_text(
                    formatted_template,
                    max_tokens=3000,
                    timeout=timeout
                )
                
                # Add section header if not present
                if not content.startswith("### 7.4"):
                    content = "### 7.4. Database Evaluation\n\n" + content
                
                # Integrate cost calculations if database cost config is available
                if "database_cost" in parsed_data:
                    self.logger.info("Integrating database cost calculations")
                    try:
                        # Initialize cost calculator
                        cost_calculator = DatabaseCostCalculator()
                        
                        # Extract recommended database types from the generated content
                        recommended_databases = self._extract_recommended_databases(content)
                        
                        # Calculate costs
                        cost_analysis = cost_calculator.calculate_database_costs(
                            parsed_data["database_cost"],
                            recommended_databases
                        )
                        
                        # Find the "Instance Selection and Cost Analysis" section and replace/enhance it
                        cost_section = self._generate_enhanced_cost_section(cost_analysis)
                        
                        # Replace or add the cost section
                        if "Instance Selection and Cost Analysis" in content:
                            # Replace existing section
                            import re
                            # Find the section header and replace everything until the next section
                            pattern = r'(#### 9\. Instance Selection and Cost Analysis)(.*?)(?=#### 10\.|$)'
                            replacement = f"\\1\n\n{cost_section}\n\n"
                            content = re.sub(pattern, replacement, content, flags=re.DOTALL)
                        else:
                            # Add new section before the final recommendation
                            if "#### 10. Final Database Recommendation" in content:
                                content = content.replace(
                                    "#### 10. Final Database Recommendation",
                                    f"#### 9. Instance Selection and Cost Analysis\n\n{cost_section}\n\n#### 10. Final Database Recommendation"
                                )
                            else:
                                # Add at the end
                                content += f"\n\n#### 9. Instance Selection and Cost Analysis\n\n{cost_section}\n\n"
                        
                        self.logger.info("Successfully integrated database cost calculations")
                    except Exception as e:
                        self.logger.error(f"Error integrating cost calculations: {str(e)}")
                        # Add a simple cost analysis placeholder
                        content += "\n\n#### 9. Instance Selection and Cost Analysis\n\n*Cost analysis could not be generated due to an error. Please refer to cloud provider pricing calculators for accurate cost estimates.*\n\n"
                
                return content
            except Exception as e:
                error_msg = f"Error generating DB evaluation section: {str(e)}"
                self.logger.error(error_msg)
                return "### 7.4. Database Evaluation\n\n*Error generating database evaluation content*"
        except Exception as e:
            error_msg = f"Error formatting template for DB evaluation: {str(e)}"
            self.logger.error(error_msg)
            return "### 7.4. Database Evaluation\n\n*Error formatting database evaluation template*"
    
    def _generate_chunked_approaches_section(self, section_name, project_name, problem_statement, 
                                           domain_insights, database_context, performance_context, 
                                           context, mermaid_diagram, architecture_insights,
                                           parsed_data: Dict[str, Any],
                                           timeout=3600, num_approaches=4) -> Dict[str, Any]:
        """
        Generate the evaluated approaches section in chunks for better reliability.
        """
        self.logger.info(f"Generating evaluated approaches in chunks with timeout {timeout}s")
        
        # Summarize PRD information
        # prd_info = self._summarize_prd(context.get("prd", "No PRD information available"))
        # Generate introduction and key challenges
        
        # Prepare conditional part separately to avoid nested f-strings (Python 3.9 compatibility)
        architecture_insights_intro = ""
        if architecture_insights:
            architecture_insights_intro = f"Architecture insights:\n{json.dumps(architecture_insights, indent=2)}"
        
        intro_prompt = f"""
You are a senior technical architect evaluating implementation approaches for a technical specification.

STRICTLY USE ONLY the following information to write the INTRODUCTION and KEY CHALLENGES for section 7.1 (Approaches Evaluation).

Project Name: {project_name}
Problem Statement: {problem_statement}

Domain Information:
{json.dumps(domain_insights, indent=2)}

{database_context}
{performance_context}

Current Architecture:
{context.get("current_architecture_description", "No description available")}

{architecture_insights_intro}

Write ONLY:
1. A brief introduction to the evaluated approaches section (1-2 paragraphs)
2. A clear statement of the key technical challenges that need to be addressed (bullet points)
3. Identification of distinct subsystems or components that require separate approach evaluations


DO NOT include any actual approaches yet - just the introduction and challenges.
"""
        
        try:
            # Generate introduction content
            self.logger.info("Generating introduction and key challenges")
            intro_content = self.bedrock_client.generate_text(
                intro_prompt,
                max_tokens=1500,
                timeout=120  # 2-minute timeout for intro
            )
        except Exception as e:
            self.logger.error(f"Error generating introduction: {str(e)}")
            intro_content = "### 7.1. Approaches Evaluation\n\n*Error generating introduction content*"
        
        approaches_content = []
        
        # First, generate a prompt to identify diverse approach types based on the problem statement
        approach_types_prompt = f"""
Based on this problem statement and domain information, identify {num_approaches} distinct architectural approaches that would be appropriate to evaluate. These should be fundamentally different approaches, not minor variations of the same approach.

Project Name: {project_name}
Problem Statement: {problem_statement}

Domain Information:
{json.dumps(domain_insights, indent=2)}

Return a JSON array of {num_approaches} distinct approach types, each with a name and brief description. For example:
IMPORTANT INSTRUCTIONS:
1. Analyze the CURRENT architecture and identify what aspects need to be preserved or improved
2. Consider the specific business requirements and technical constraints in the problem statement
3. Evaluate approaches that build upon the existing architecture when appropriate, rather than replacing it entirely
4. Only suggest complete architectural changes if the current approach is fundamentally inadequate
5. Focus on approaches that are specifically tailored to this problem domain and requirements
6.Make sure each approach is technically distinct from the others and appropriate for the specific problem domain.
"""

        try:
            # Generate approach types
            self.logger.info("Generating approach types")
            approach_types_text = self.bedrock_client.generate_text(
                approach_types_prompt,
                max_tokens=1500,
                timeout=120
            )
            
            # Parse the JSON
            try:
                import re
                json_match = re.search(r'\[[\s\S]*\]', approach_types_text)
                if json_match:
                    approach_types = json.loads(json_match.group(0))
                else:
                    raise ValueError("Could not find JSON array in response")
            except Exception as e:
                self.logger.warning(f"Failed to parse approach types: {str(e)}")
                # Fallback to generic approach types
                approach_types = [
                    {"name": f"Approach Type {i}", "description": "Generic approach"} 
                    for i in range(1, num_approaches + 1)
                ]
        except Exception as e:
            self.logger.error(f"Error generating approach types: {str(e)}")
            approach_types = [
                {"name": f"Approach Type {i}", "description": "Generic approach"} 
                for i in range(1, num_approaches + 1)
            ]
        
        # Generate each approach separately
        for i in range(1, num_approaches + 1):
            # Get the approach type for this iteration
            approach_type = approach_types[i-1] if i <= len(approach_types) else {"name": f"Alternative Approach {i}", "description": "Generic approach"}
            
            # Prepare conditional part separately to avoid nested f-strings (Python 3.9 compatibility)
            mermaid_diagram_section = ""
            if mermaid_diagram:
                mermaid_diagram_section = f"Current Architecture Diagram (Mermaid):\n```mermaid\n{mermaid_diagram}\n```"
            
            approach_prompt = f"""
You are a senior technical architect evaluating implementation approaches for a technical specification.

STRICTLY USE ONLY the following information to write a detailed description of Approach {i} of {num_approaches} for section 7.1.

Project Name: {project_name}
Problem Statement: {problem_statement}

Domain Information:
{json.dumps(domain_insights, indent=2)}

{database_context}
{performance_context}

Current Architecture:
{context.get("current_architecture_description", "No description available")}

{mermaid_diagram_section}

For Approach {i}, provide a solution based on "{approach_type['name']}" ({approach_type['description']}) with:
1. A specific, descriptive name (e.g., "Approach {i}: {approach_type['name']}")
2. A comprehensive technical description of the approach architecture in a professional, concise tone
3. A block diagram in Mermaid format illustrating the approach
4. A sequence diagram in Mermaid format showing the request flow
5. Details of the specific components, services, and technologies involved with exact names
6. Explanation of the data flow and processing logic with step-by-step sequences
7. Documentation of the integration patterns and interfaces with specific API details
8. Pros and cons in bullet point format
9. Implementation complexity, cost implications, and timeline considerations

Format your response with proper markdown:
#### Approach {i}: [Your descriptive name]

[Concise technical description of the approach]

[Block diagram in Mermaid format]

[Sequence diagram in Mermaid format]

**Pros:**
- [List advantages as bullet points]

**Cons:**
- [List disadvantages as bullet points]

CRITICAL FORMATTING REQUIREMENT:
You MUST start your response with EXACTLY this heading format:
#### Approach {i}: [Your descriptive name]

Do NOT use any other heading format. This is mandatory for proper document structure.

IMPORTANT:
- Use Mermaid diagram syntax for architecture diagrams and sequence diagrams
- Use a professional color scheme with blues (#3498db, #2980b9), grays (#95a5a6, #7f8c8d), and dark text (#2c3e50)
- NEVER use pink, purple, or bright red colors in the diagrams
- Use bullet points for pros/cons
- Maintain a professional, concise technical writing style
- Include specific technical details like API specifications, data models, and configuration parameters
- Make this approach SIGNIFICANTLY different from other approaches
- Ensure this approach is based on "{approach_type['name']}" but tailored to the specific problem
"""
            
            try:
                # Generate approach content
                self.logger.info(f"Generating content for Approach {i}")
                approach_content = self.bedrock_client.generate_text(
                    approach_prompt,
                    max_tokens=2000,
                    timeout=int(timeout / (num_approaches + 5))  # Divide timeout among approaches plus other sections
                )
                approaches_content.append(approach_content)
            except Exception as e:
                self.logger.error(f"Error generating Approach {i}: {str(e)}")
                approaches_content.append(f"#### Approach {i}\n\n*Error generating approach content*")
        
        # Generate comparative analysis and recommendation
        comparison_prompt = f"""
You are a senior technical architect evaluating implementation approaches for a technical specification.

You have already described {num_approaches} different approaches. Now create the final part of section 7.1 with:

1. A comparative analysis table showing how each approach performs against key evaluation criteria such as:
   - Performance characteristics
   - Scalability considerations
   - Operational complexity
   - Development effort
   - Cost implications
   - Risk factors
   - Compatibility with existing systems

2. A final recommendation with justification for the selected approach
3. A brief implementation roadmap for the selected approach

Format your response with proper markdown:

#### Comparative Analysis

[Comparison table with approaches as columns and criteria as rows]

#### Final Recommendation

[Clear statement of the recommended approach with justification]

#### Implementation Roadmap

[Brief roadmap for implementing the selected approach]
"""
        
        try:
            # Generate comparison content
            self.logger.info("Generating comparative analysis and recommendation")
            comparison_content = self.bedrock_client.generate_text(
                comparison_prompt,
                max_tokens=2000,
                timeout=int(timeout / (num_approaches + 5))
            )
        except Exception as e:
            self.logger.error(f"Error generating comparative analysis: {str(e)}")
            comparison_content = "#### Comparative Analysis\n\n*Error generating comparative analysis content*"
        
        if database_context != "":

        # Generate data model changes section (7.2)
            data_model_prompt = f"""
    You are a senior technical architect documenting data model changes for a technical specification.

    STRICTLY USE ONLY the following information to write section 7.2 (Data model/Schema Changes).

    Project Name: {project_name}
    Problem Statement: {problem_statement}

    Domain Information:
    {json.dumps(domain_insights, indent=2)}

    {database_context}

    Current Architecture:
    {context.get("current_architecture_description", "No description available")}

    Write a comprehensive section on data model/schema changes with:
    1. Clear header "### 7.2. Data model/Schema Changes"
    2. Description of all database schema changes required for this project
    3. Entity-relationship diagrams using Mermaid where appropriate
    4. Table structure changes with field names, types, constraints
    5. Index changes and optimization considerations
    6. Migration strategy and backward compatibility considerations

    If no database changes are required, clearly state that.
    """
            
            try:
                # Generate data model changes content
                self.logger.info("Generating data model changes section")
                data_model_content = self.bedrock_client.generate_text(
                    data_model_prompt,
                    max_tokens=2000,
                    timeout=int(timeout / (num_approaches + 5))
                )
                
                # Ensure proper section header
                if not data_model_content.startswith("### 7.2"):
                    data_model_content = "### 7.2. Data model/Schema Changes\n\n" + data_model_content
            except Exception as e:
                self.logger.error(f"Error generating data model changes: {str(e)}")
                data_model_content = "### 7.2. Data model/Schema Changes\n\n*Error generating data model changes content*"
        else:
            data_model_content = ""
        # Generate business logic changes section (7.3)
        business_logic_prompt = f"""
You are a senior technical architect documenting business logic changes for a technical specification.

STRICTLY USE ONLY the following information to write section 7.3 (Business Logic Changes).

Project Name: {project_name}
Problem Statement: {problem_statement}

Domain Information:
{json.dumps(domain_insights, indent=2)}

Current Architecture:
{context.get("current_architecture_description", "No description available")}

Write a comprehensive section on business logic changes with:
1. Clear header "### 7.3. Business Logic Changes"
2. Description of all business logic changes required for this project
3. Flow diagrams using Mermaid where appropriate
"""
        if (parsed_data.get("api_documentation").get("type") != "none"):
            business_logic_prompt += """
        4. API changes with request/response formats
        """
        business_logic_prompt += """
5. Algorithm changes and processing logic modifications
6. Integration changes with external systems

If no business logic changes are required, clearly state that.
"""
        
        try:
            # Generate business logic changes content
            self.logger.info("Generating business logic changes section")
            business_logic_content = self.bedrock_client.generate_text(
                business_logic_prompt,
                max_tokens=2000,
                timeout=int(timeout / (num_approaches + 5))
            )
            
            # Ensure proper section header
            if not business_logic_content.startswith("### 7.3"):
                business_logic_content = "### 7.3. Business Logic Changes\n\n" + business_logic_content
        except Exception as e:
            self.logger.error(f"Error generating business logic changes: {str(e)}")
            business_logic_content = "### 7.3. Business Logic Changes\n\n*Error generating business logic changes content*"
        
        # Generate DB evaluation section (7.4) if database context is available
        db_evaluation_content = ""
        if database_context != "":
            try:
                db_evaluation_content = self._generate_db_evaluation_section(
                    project_name, 
                    problem_statement, 
                    parsed_data, 
                    timeout=int(timeout / (num_approaches + 5))
                )
            except Exception as e:
                self.logger.error(f"Error generating DB evaluation: {str(e)}")
                db_evaluation_content = "### 7.4. Database Evaluation\n\n*Error generating database evaluation content*"
        
        # Combine all content
        combined_content = f"""### 7.1. Approaches Evaluation

{intro_content}

{"".join(approaches_content)}

{comparison_content}

{data_model_content}

{business_logic_content}

{db_evaluation_content}
"""
        
        return {
            "title": section_name,
            "content": combined_content
        }    
    def _generate_architecture_diagram(self, context: Dict[str, Any]) -> str:
        """
        Generate an architecture diagram for the technical specification.
        
        Args:
            context: Context dictionary with information about the project
            
        Returns:
            Generated architecture diagram in Mermaid format
        """
        self.logger.info("Generating architecture diagram")
        
        # Get prompt template
        prompt_template = self.prompt_templates.get("architecture_diagram", "")
        
        # Format prompt with context
        prompt = prompt_template.format(**context)
        
        try:
            self.logger.info("Calling Bedrock to generate architecture diagram")
            architecture_diagram = self.bedrock_client.generate_text(
                prompt, 
                max_tokens=4096,
                temperature=0.7,
                timeout=60  # 1 minute timeout
            )
            
            # Extract the Mermaid diagram if it's wrapped in markdown code blocks
            if "```mermaid" in architecture_diagram:
                architecture_diagram = architecture_diagram.split("```mermaid")[1]
                if "```" in architecture_diagram:
                    architecture_diagram = architecture_diagram.split("```")[0].strip()
            
            self.logger.info("Successfully generated architecture diagram")
            return architecture_diagram
        except Exception as e:
            self.logger.error(f"Failed to generate architecture diagram: {str(e)}")
            raise RuntimeError(f"Failed to generate architecture diagram: {str(e)}")


    def _analyze_image_architecture(self, image_path: str) -> str:
        """
        Analyze an architecture diagram image and generate a Mermaid diagram.
        
        Args:
            image_path: Path to the architecture diagram image
            
        Returns:
            Mermaid diagram representation of the architecture
        """
        self.logger.info(f"Analyzing architecture image: {image_path}")
        
        try:
            mermaid_diagram = self.bedrock_client.analyze_image_architecture(image_path, "")
            self.logger.info("Successfully analyzed architecture image")
            return mermaid_diagram
        except Exception as e:
            self.logger.error(f"Failed to analyze architecture image: {str(e)}")
            raise RuntimeError(f"Failed to analyze architecture image: {str(e)}")

    def _prepare_context(self, project_name: str, problem_statement: str, 
                        parsed_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Prepare context information for the prompt.
        
        Args:
            project_name: Name of the project
            problem_statement: Problem statement text
            parsed_data: Dictionary of parsed input data
            
        Returns:
            Context dictionary
        """
        # Initialize with required template variables and default values
        context = {
            "project_name": project_name,
            "problem_statement": problem_statement,
            "business_context": parsed_data.get("business_context", ""),
            "current_challenges": parsed_data.get("current_challenges", ""),
            "additional_context": parsed_data.get("additional_context", ""),
            "current_state": "",
            "project_goals": "",
            # Add default values for all possible template variables
            "scope": parsed_data.get("scope", ""),
            "goals": parsed_data.get("goals", ""),
            "non_goals": parsed_data.get("non_goals", ""),
            "assumptions": parsed_data.get("assumptions", ""),
            "out_of_scope": parsed_data.get("out_of_scope", ""),
            "futuristic_scope": parsed_data.get("futuristic_scope", ""),
            "dependencies": parsed_data.get("dependencies", ""),
            "testing_plan": parsed_data.get("testing_plan", ""),
            "go_live_plan": parsed_data.get("go_live_plan", ""),
            "monitoring_logging": parsed_data.get("monitoring_logging", ""),
            "milestones_timelines": parsed_data.get("milestones_timelines", ""),
            # Add missing variables that are causing warnings
            "external_services": parsed_data.get("external_services", ""),
            "api_dependencies": parsed_data.get("api_dependencies", ""),
            "sla_requirements": parsed_data.get("sla_requirements", ""),
            "integration_points": parsed_data.get("integration_points", ""),
            "rollout_plan": parsed_data.get("rollout_plan", ""),
            "backward_compatibility": parsed_data.get("backward_compatibility", ""),
            "rollback_plan": parsed_data.get("rollback_plan", ""),
            "deployment_strategy": parsed_data.get("deployment_strategy", ""),
            "release_phases": parsed_data.get("release_phases", ""),
            "feature_flags": parsed_data.get("feature_flags", ""),
            "monitoring_during_rollout": parsed_data.get("monitoring_during_rollout", ""),
            "communication_plan": parsed_data.get("communication_plan", ""),
            # Add default values for database-related fields
            "workload_type": "Not specified",
            "acid_requirements": "Not specified",
            "join_complexity": "Not specified",
            "failure_points_details": "Not specified",
            "transaction_boundaries_details": "Not specified",
            "international_support": "Yes, international support is required",
            "data_archival": "Not specified",
            "normalization": "Not specified",
            "database_purpose": "Not specified",
            "query_type": "Not specified",
            # Add default empty values for Context Generator fields
            "apis": [],
            "flows": [],
            "jobs": [],
            "external_calls": [],
            "db_operations": [],
            "failure_points": [],
            "retry_mechanisms": [],
            "idempotency_mechanisms": [],
            "nfrlist": parsed_data.get("nfrlist")
        }
        
        # Extract current architecture description
        current_architecture_description = ""
        if "architecture" in parsed_data:
            arch_data = parsed_data["architecture"]
            if "content" in arch_data and isinstance(arch_data["content"], str) and not arch_data.get("type") == "image":
                current_architecture_description = arch_data["content"]
        context["current_architecture_description"] = current_architecture_description
        
        # Extract evaluated approaches if available
        evaluated_approaches = []
        selected_approach = {}
        if "evaluated_approaches" in parsed_data:
            evaluated_approaches = parsed_data.get("evaluated_approaches", [])
            # Try to find the selected approach
            for approach in evaluated_approaches:
                if approach.get("selected", False):
                    selected_approach = approach
                    break
        context["evaluated_approaches"] = evaluated_approaches
        context["selected_approach"] = selected_approach
        
        # Extract business logic changes if available
        business_logic_changes = parsed_data.get("business_logic_changes", {})
        context["business_logic_changes"] = business_logic_changes
        
        # Extract data model changes if available
        data_model_changes = parsed_data.get("data_model_changes", {})
        context["data_model_changes"] = data_model_changes
        
        # Extract database information if available
        if "database" in parsed_data:
            db_data = parsed_data["database"]
            # Store all database parameters except type (which will be recommended)
            context["anticipate_changes"] = db_data.get("anticipate_changes", "Not specified")
            context["workload_type"] = db_data.get("workload_type", "Not specified")
            context["acid_requirements"] = db_data.get("acid_requirements", "Not specified")
            context["archival_policy"] = db_data.get("archival_policy", "Not specified")
            context["international_support"] = db_data.get("international_support", "Yes, international support is required")
            context["highlight_failure_points"] = db_data.get("highlight_failure_points", "Not specified")
            context["failure_points_details"] = db_data.get("failure_points_details", "Not specified")
            context["idempotency_critical"] = db_data.get("idempotency_critical", "Not specified")
            context["transaction_boundaries"] = db_data.get("transaction_boundaries", "Not specified")
            context["transaction_boundaries_details"] = db_data.get("transaction_boundaries_details", "Not specified")
            context["join_complexity"] = db_data.get("join_complexity", "Not specified")
            context["data_archival"] = db_data.get("data_archival", "Not specified")
            context["transactions_importance"] = db_data.get("transactions_importance", "Not specified")
            context["normalization"] = db_data.get("normalization", "Not specified")
            context["database_purpose"] = db_data.get("database_purpose", "Not specified")
            context["query_type"] = db_data.get("query_type", "Not specified")
            context["db_details"] = db_data.get("details", "Not specified")
        
        # Extract Context Generator data if available
        if "context_generator" in parsed_data:
            context_gen_data = parsed_data["context_generator"]
            analysis_results = context_gen_data.get("analysis_results", {})
            
            # Add Context Generator results to context
            context["context_generator"] = {
                "output_dir": context_gen_data.get("output_dir", ""),
                "generated_files": context_gen_data.get("generated_files", [])
            }
            
            # Add specific analysis results to context
            context["apis"] = analysis_results.get("apis", [])
            context["flows"] = analysis_results.get("flows", [])
            context["jobs"] = analysis_results.get("jobs", [])
            context["external_calls"] = analysis_results.get("external_calls", [])
            context["db_operations"] = analysis_results.get("db_operations", [])
            context["failure_points"] = analysis_results.get("failure_points", [])
            context["retry_mechanisms"] = analysis_results.get("retry_mechanisms", [])
            context["idempotency_mechanisms"] = analysis_results.get("idempotency_mechanisms", [])
            
            # Enhance failure points details with Context Generator data if available
            if analysis_results.get("failure_points") and not context["failure_points_details"]:
                failure_points_summary = "\n".join([
                    f"- {fp.get('location', 'Unknown location')}: {fp.get('description', 'No description')}"
                    for fp in analysis_results.get("failure_points", [])[:5]  # Limit to first 5 for brevity
                ])
                if failure_points_summary:
                    context["failure_points_details"] = f"Identified failure points from code analysis:\n{failure_points_summary}"
            
            # Add API endpoints to enhance API documentation
            if analysis_results.get("apis") and "code" in context:
                if "api_endpoints" not in context["code"]:
                    context["code"]["api_endpoints"] = {}
                context["code"]["api_endpoints"]["context_generator_apis"] = analysis_results.get("apis", [])
        
        # Extract NFRs if available
        if "nfrlist" in parsed_data:
            nfrlist = parsed_data["nfrlist"]
        else:
            nfrlist = ["scalability", "availability", "security", "compliance", "reliability", "infra_cost", 
                            "performance", "maintainability", "observability", "data_management"]
        nfr = {}
        for nfr_category in nfrlist:
            if nfr_category in parsed_data:
                nfr[nfr_category] = parsed_data[nfr_category]
        context["nfr"] = nfr
        context["nfrlist"] = nfrlist
        
        # Extract goals and scope if available
        context["goals"] = parsed_data.get("goals", "")
        context["scope"] = parsed_data.get("scope", "")
        context["out_of_scope"] = parsed_data.get("out_of_scope", "")
        context["futuristic_scope"] = parsed_data.get("futuristic_scope", "")
        context["assumptions"] = parsed_data.get("assumptions", "")
        context["dependencies"] = parsed_data.get("dependencies", "")
        
        # Extract testing and deployment information if available
        context["testing_plan"] = parsed_data.get("testing_plan", "")
        context["go_live_plan"] = parsed_data.get("go_live_plan", "")
        context["monitoring_logging"] = parsed_data.get("monitoring_logging", "")
        context["milestones_timelines"] = parsed_data.get("milestones_timelines", "")
        
        # Add parsed data from PRD
        if "prd" in parsed_data:
            prd_data = parsed_data["prd"]
            context["prd"] = prd_data
            
            # Extract additional context from PRD if available
            if isinstance(prd_data, dict):
                # Only overwrite if the fields are empty and PRD has values
                if not context["business_context"] and prd_data.get("business_context"):
                    context["business_context"] = prd_data.get("business_context", "")
                if not context["current_state"] and prd_data.get("current_state"):
                    context["current_state"] = prd_data.get("current_state", "")
                if not context["project_goals"] and prd_data.get("project_goals"):
                    context["project_goals"] = prd_data.get("project_goals", "")
        
        if "architecture" in parsed_data:
            # Include architecture data but handle image data carefully
            arch_data = parsed_data["architecture"]
            if arch_data.get("type") == "image":
                # For images, include file name and path but not the base64 data
                context["architecture"] = {
                    "type": "image",
                    "file_name": arch_data.get("file_name", ""),
                    "file_path": arch_data.get("content", ""),
                    "image_type": arch_data.get("image_type", "")
                }
                
                # Extract architecture insights if available
                if "metadata" in arch_data and "architecture_insights" in arch_data.get("metadata", {}):
                    context["architecture_insights"] = arch_data["metadata"]["architecture_insights"]
            else:
                context["architecture"] = arch_data
        
        if "code" in parsed_data:
            # Extract more detailed code information
            code_data = parsed_data["code"]
            detailed_code = {
                "languages": code_data.get("languages", {}),
                "important_files": code_data.get("important_files", {}),
                "dependencies": code_data.get("dependencies", {}),
                "architecture_patterns": code_data.get("architecture_patterns", {}),
                "api_endpoints": code_data.get("api_endpoints", {}),
                "database_schemas": code_data.get("database_schemas", {}),
                "key_components": code_data.get("key_components", {})
            }
            context["code"] = detailed_code
            
            # Extract component details if available
            if "components" in code_data:
                context["components"] = code_data["components"]
            
            # Extract relationships between components if available
            if "relationships" in code_data:
                context["relationships"] = code_data["relationships"]
        
        # Inject Razorpay service context for all sections
        # Check if specific service names are provided in parsed_data
        service_names = parsed_data.get("service_names") or parsed_data.get("related_services", [])
        
        if service_names:
            # Dynamically fetch context for specific services
            self.logger.info(f"Fetching context for user-specified services: {service_names}")
            service_context = self.service_context_manager.get_contexts_for_services(service_names)
        else:
            # Fall back to configured services (if any)
            service_context = self.service_context_manager.get_all_service_contexts()
        
        if service_context:
            # Add service context to additional_context
            existing_context = context.get("additional_context", "")
            context["additional_context"] = existing_context + service_context if existing_context else service_context
            self.logger.debug("Injected service context into specification generation")
        
        return context
    
    def _extract_recommended_databases(self, content: str) -> List[str]:
        """
        Extract recommended database types from the generated content.
        
        Args:
            content: Generated database evaluation content
            
        Returns:
            List of recommended database types
        """
        recommended_databases = []
        
        # Common database types to look for
        database_types = [
            "PostgreSQL", "MySQL", "MongoDB", "CockroachDB", "Oracle", 
            "SQL Server", "SQLite", "Redis", "Cassandra", "DynamoDB",
            "ClickHouse", "TiDB", "Elasticsearch", "Solr", "Rockset",
            "Aurora", "DocumentDB", "CosmosDB", "Firestore", "BigQuery"
        ]
        
        content_lower = content.lower()
        
        # First, try to find the "Final Database Recommendation" section
        final_recommendation_section = ""
        lines = content.split('\n')
        in_final_recommendation = False
        
        for line in lines:
            line_lower = line.lower().strip()
            
            # Look for the start of the final recommendation section
            if any(marker in line_lower for marker in [
                "final database recommendation",
                "final recommendation", 
                "recommended database",
                "database recommendation",
                "primary database recommendation"
            ]):
                in_final_recommendation = True
                final_recommendation_section = line + "\n"
                continue
            
            # If we're in the final recommendation section, keep collecting lines
            if in_final_recommendation:
                # Stop if we hit another major section
                if line.startswith("##") and line_lower not in ["final database recommendation", "final recommendation"]:
                    break
                final_recommendation_section += line + "\n"
        
        # If we found a final recommendation section, extract databases from it
        if final_recommendation_section:
            self.logger.info("Found Final Database Recommendation section, extracting databases")
            final_section_lower = final_recommendation_section.lower()
            
            # Look for explicit statements like "recommend PostgreSQL" or "PostgreSQL is recommended"
            for db_type in database_types:
                db_lower = db_type.lower()
                
                # Check for explicit recommendation patterns
                recommendation_patterns = [
                    f"recommend {db_lower}",
                    f"{db_lower} is recommended",
                    f"primary solution: {db_lower}",
                    f"primary database: {db_lower}",
                    f"best fit: {db_lower}",
                    f"optimal choice: {db_lower}",
                    f"selected database: {db_lower}",
                    f"chosen database: {db_lower}",
                    f"final choice: {db_lower}",
                    f"go with {db_lower}",
                    f"use {db_lower} as"
                ]
                
                if any(pattern in final_section_lower for pattern in recommendation_patterns):
                    recommended_databases.append(db_type)
                    self.logger.info(f"Found explicit recommendation for {db_type}")
        
        # If no explicit recommendations found in final section, fall back to general extraction
        if not recommended_databases:
            self.logger.info("No explicit recommendations found in final section, using general extraction")
            
            # Look for databases mentioned in recommendation contexts throughout the content
            for db_type in database_types:
                db_lower = db_type.lower()
                
                # Check if database is mentioned near recommendation keywords
                if db_lower in content_lower:
                    # Create a context window around the database mention
                    db_index = content_lower.find(db_lower)
                    if db_index != -1:
                        # Get 200 characters before and after the mention
                        context_start = max(0, db_index - 200)
                        context_end = min(len(content_lower), db_index + len(db_lower) + 200)
                        context_window = content_lower[context_start:context_end]
                        
                        # Check if recommendation keywords appear in the context window
                        if any(keyword in context_window for keyword in [
                            "recommend", "recommended", "suggestion", "suggested", 
                            "primary", "best", "optimal", "final", "chosen", 
                            "selected", "preferred", "ideal", "appropriate"
                        ]):
                            recommended_databases.append(db_type)
                            self.logger.info(f"Found contextual recommendation for {db_type}")
        
        # Remove duplicates while preserving order
        recommended_databases = list(dict.fromkeys(recommended_databases))
        
        # If still no recommendations found, provide sensible defaults based on content
        if not recommended_databases:
            self.logger.warning("No database recommendations found, using default recommendations")
            
            # Analyze content for clues about appropriate databases
            if any(keyword in content_lower for keyword in ["document", "json", "schema-less", "flexible"]):
                recommended_databases = ["MongoDB", "PostgreSQL"]
            elif any(keyword in content_lower for keyword in ["relational", "sql", "acid", "joins"]):
                recommended_databases = ["PostgreSQL", "MySQL"]
            elif any(keyword in content_lower for keyword in ["search", "full-text", "analytics"]):
                recommended_databases = ["Elasticsearch", "PostgreSQL"]
            else:
                recommended_databases = ["PostgreSQL", "MySQL", "MongoDB"]
        
        self.logger.info(f"Final extracted database recommendations: {recommended_databases}")
        return recommended_databases
    
    def _generate_enhanced_cost_section(self, cost_analysis: Dict[str, Any]) -> str:
        """
        Generate an enhanced cost section with the calculated costs.
        
        Args:
            cost_analysis: Cost analysis results from DatabaseCostCalculator
            
        Returns:
            Enhanced cost section content
        """
        section_content = ""
        
        # Add working set calculation
        if "working_set_calculation" in cost_analysis:
            section_content += cost_analysis["working_set_calculation"] + "\n\n"
        
        # Add storage growth analysis
        if "storage_growth_analysis" in cost_analysis:
            section_content += cost_analysis["storage_growth_analysis"] + "\n\n"
        
        # Add cost comparison table
        if "cost_comparison_table" in cost_analysis:
            section_content += "**Cost Comparison (Monthly Estimates):**\n\n"
            section_content += cost_analysis["cost_comparison_table"] + "\n\n"
        
        # Add user requirements summary
        if "user_requirements" in cost_analysis:
            reqs = cost_analysis["user_requirements"]
            section_content += "**Configuration Details:**\n"
            section_content += f"- Storage Requirement: {reqs['storage_gb']}GB\n"
            section_content += f"- Expected IOPS: {reqs.get('iops_level', 'Not specified')}\n"
            section_content += f"- Storage Growth Rate: {reqs.get('storage_growth_rate', 'Not specified')}\n"
            section_content += f"- High Availability: {'Yes' if reqs['high_availability'] else 'No'}\n"
            section_content += f"- Backup Retention: {reqs['backup_retention_days']} days\n"
            section_content += f"- Read Replicas: {reqs['read_replicas']}\n"
            section_content += f"- Cloud Providers: {', '.join(reqs['cloud_providers'])}\n\n"
        
        # Add cost analysis insights
        if "database_options" in cost_analysis and cost_analysis["database_options"]:
            options = cost_analysis["database_options"]
            sorted_options = sorted(options, key=lambda x: x.total_monthly_cost)
            
            section_content += "**Cost Analysis Insights:**\n"
            section_content += f"- Most cost-effective option: {sorted_options[0].database_type} (${sorted_options[0].total_monthly_cost:.2f}/month)\n"
            section_content += f"- Most expensive option: {sorted_options[-1].database_type} (${sorted_options[-1].total_monthly_cost:.2f}/month)\n"
            
            cost_range = sorted_options[-1].total_monthly_cost - sorted_options[0].total_monthly_cost
            section_content += f"- Cost range: ${cost_range:.2f}/month difference\n\n"
        
        # Generate specific recommendation using prompt (integrated directly)
        if "database_options" in cost_analysis and cost_analysis["database_options"]:
            try:
                # Get the most cost-effective option
                options = cost_analysis["database_options"]
                sorted_options = sorted(options, key=lambda x: x.total_monthly_cost)
                best_option = sorted_options[0]
                
                # Get user requirements
                reqs = cost_analysis["user_requirements"]
                iops_level = reqs.get("iops_level", "Medium (1000-5000 IOPS)")
                
                # Extract actual calculated data from working set calculation
                working_set_text = cost_analysis.get("working_set_calculation", "")
                
                # Parse the working set calculation to extract real numbers
                import re
                actual_iops = 2500  # default fallback
                daily_operations = 0
                monthly_operations = 0
                daily_data_gb = 0
                monthly_data_gb = 0
                
                # Extract actual calculated values from working set calculation
                iops_match = re.search(r'~(\d+(?:,\d+)*) IOPS', working_set_text)
                if iops_match:
                    actual_iops = int(iops_match.group(1).replace(',', ''))
                
                daily_match = re.search(r'Daily database operations: ([\d,]+)', working_set_text)
                if daily_match:
                    daily_operations = int(daily_match.group(1).replace(',', ''))
                
                monthly_match = re.search(r'Monthly database operations: ([\d,]+)', working_set_text)
                if monthly_match:
                    monthly_operations = int(monthly_match.group(1).replace(',', ''))
                
                daily_data_match = re.search(r'Daily data volume: ~([\d.]+)GB', working_set_text)
                if daily_data_match:
                    daily_data_gb = float(daily_data_match.group(1))
                
                monthly_data_match = re.search(r'Monthly data volume: ~([\d.]+)GB', working_set_text)
                if monthly_data_match:
                    monthly_data_gb = float(monthly_data_match.group(1))
                
                # Calculate memory-to-workload ratio
                memory_gb = best_option.primary_instance.memory_gb
                memory_per_iops = memory_gb * 1024 / actual_iops if actual_iops > 0 else 0  # MB per IOPS
                
                # Determine workload characteristics dynamically based on actual data
                if daily_data_gb > 0 and monthly_operations > 0:
                    avg_read_write_ratio = "Read-heavy" if daily_data_gb < (monthly_operations / 30 * 0.001) else "Write-heavy"
                else:
                    avg_read_write_ratio = "Mixed read/write"
                
                # Create dynamic prompt using actual calculated data
                prompt = f"""
You are a database architect providing a specific instance recommendation. Based on the ACTUAL calculated cost analysis data, generate a professional recommendation in this exact format:

**Recommendation:**
{best_option.primary_instance.instance_type} is the optimal choice for this service based on:
- [Analyze the {memory_gb}GB memory for {actual_iops} IOPS workload - provide specific technical reasoning]
- Appropriate for workload characteristics:
  - {avg_read_write_ratio} operations (based on {daily_data_gb:.1f}GB daily data volume)
  - [Analyze query complexity based on storage and throughput requirements]
  - Peak throughput: {actual_iops} IOPS ({daily_operations:,} daily operations)
- Cost efficiency

ACTUAL CALCULATED DATA (use these real numbers, not assumptions):
- Recommended Instance: {best_option.primary_instance.instance_type}
- Database Type: {best_option.database_type}
- vCPUs: {best_option.primary_instance.vcpus}
- Memory: {memory_gb}GB
- Storage: {best_option.primary_instance.storage_gb}GB
- Monthly Cost: ${best_option.total_monthly_cost:.2f}
- ACTUAL IOPS: {actual_iops} IOPS
- ACTUAL Daily Operations: {daily_operations:,}
- ACTUAL Monthly Operations: {monthly_operations:,}
- ACTUAL Daily Data: {daily_data_gb:.1f}GB
- ACTUAL Monthly Data: {monthly_data_gb:.1f}GB
- Memory per IOPS: {memory_per_iops:.1f}MB per IOPS
- IOPS Level: {iops_level}
- High Availability: {reqs.get("high_availability", False)}
- Read Replicas: {reqs.get("read_replicas", 0)}

INSTRUCTIONS:
1. Use the ACTUAL calculated numbers above (IOPS: {actual_iops}, Daily Data: {daily_data_gb:.1f}GB, etc.)
2. Analyze the memory-to-workload ratio: {memory_per_iops:.1f}MB per IOPS
3. Base workload characteristics on ACTUAL data patterns, not assumptions
4. Mention specific technical reasons why this instance size fits the calculated workload
5. Reference cost efficiency as a key factor
6. Keep the format professional and concise
7. Use the REAL calculated values, not generic estimates

Provide ONLY the recommendation in the specified format, nothing else.
"""
                
                # Generate recommendation
                specific_recommendation = self.bedrock_client.generate_text(
                    prompt,
                    max_tokens=300,
                    timeout=30
                )
                
                # Clean up and format the response
                if not specific_recommendation.startswith("**Recommendation:**"):
                    specific_recommendation = "**Recommendation:**\n" + specific_recommendation
                
                section_content += specific_recommendation.strip() + "\n\n"
                
            except Exception as e:
                self.logger.error(f"Error generating specific recommendation: {str(e)}")
                # Fallback to a simple recommendation
                section_content += f"**Recommendation:**\n{best_option.primary_instance.instance_type} is the optimal choice for this service based on cost efficiency and appropriate resource allocation for {iops_level.lower()} IOPS workloads.\n\n"
        
        # Add general cost optimization recommendations
        section_content += "**Cost Optimization Recommendations:**\n"
        section_content += "- Start with the most cost-effective option that meets your performance requirements\n"
        section_content += "- Consider using read replicas only if read performance becomes a bottleneck\n"
        section_content += "- Monitor actual usage and adjust instance sizes accordingly\n"
        section_content += "- Implement automated backup policies to optimize storage costs\n"
        section_content += "- Consider reserved instances or committed use discounts for long-term cost savings\n"
        section_content += "- Plan for storage growth to avoid unexpected cost increases\n\n"
        
        return section_content.strip()

    def _summarize_prd(self, prd_path: str) -> str:
        """
        Summarize the PRD using the PRDAnalyzer.
        
        Args:
            prd_path: Path to the PRD document.
            
        Returns:
            A summarized version of the PRD.
        """
        try:
            # Initialize PRDAnalyzer
            prd_analyzer = PRDAnalyzer(self.config)
            
            # Analyze the PRD to extract key information
            analysis_data = prd_analyzer.analyze(prd_path)
            
            # Create a summary from the extracted data
            summary_parts = []
            for key in ["introduction", "scope", "goals", "assumptions"]:
                if key in analysis_data:
                    summary_parts.append(f"{key.capitalize()}: {analysis_data[key]}")
            
            # Join the summary parts into a single string
            summary = "\n".join(summary_parts)
            print("summary", summary)
            print("analysis_data", analysis_data)
            return analysis_data
        except Exception as e:
            self.logger.error(f"Error summarizing PRD: {str(e)}")
            return "Error summarizing PRD."

   
def get_custom_nfr_prompt(formatted_template, nfrlist):
    """
    Get a custom NFR prompt for the given formatted template.
    """
    if "performance" in nfrlist:
        formatted_template += """
    a. Performance:
    - Specific throughput requirements (e.g., transactions per second, requests per minute)
    - Response time targets with percentiles (e.g., p95, p99)
    - Latency budgets for critical operations
    - Batch processing time windows and SLAs
    - Include a table with operation-specific performance targets
    - Consider the database workload type and query patterns
    """
    if "scalability" in nfrlist:
        formatted_template += """
    b. Scalability:
        - Horizontal and vertical scaling requirements
        - Expected growth patterns and scaling triggers
        - Auto-scaling policies and thresholds
        - Resource utilization targets (CPU, memory, I/O)
        - Capacity planning guidelines
        - Include specific metrics and thresholds in tabular format
        - Consider the database purpose and anticipated changes
    """
    if "availability" in nfrlist:
        formatted_template += """
    c. Availability:
        - Uptime requirements (e.g., 99.99%)
        - Scheduled maintenance windows
        - Failover requirements and recovery time objectives (RTO)
        - Disaster recovery strategy
        - Multi-region or multi-zone requirements
        - Include a table with availability targets and recovery metrics
        - Consider the transactions importance
    """
    if "reliability" in nfrlist:
        formatted_template += """
    d. Reliability:
        - Mean time between failures (MTBF) targets
        - Fault tolerance requirements
        - Circuit breaking thresholds
        - Retry policies with specific parameters
        - Graceful degradation strategies
        - Include specific reliability metrics and thresholds
        - Address potential failure points
        - Consider idempotency requirements
        - Address transaction boundary considerations
    """
    if "security" in nfrlist:
        formatted_template += """
    e. Security:
        - Authentication and authorization requirements
        - Data encryption standards (at rest and in transit)
        - Access control policies
        - Security compliance requirements (e.g., SOC2, PCI-DSS, GDPR)
        - Penetration testing requirements
        - Audit logging requirements
        - Include specific security controls and standards
        - Consider international data requirements if applicable
    """

    if "compliance" in nfrlist:
        formatted_template += """
    f. Compliance:
        - Regulatory requirements
        - Industry standards
        - Internal compliance policies
        - Audit requirements
        - Data retention policies
        - Include specific compliance standards and controls
        - Consider international compliance requirements if applicable
    """

    if "maintainability" in nfrlist:
        formatted_template += """
    g. Maintainability:
        - Code quality standards
        - Documentation requirements
        - Monitoring and observability requirements
        - Deployment frequency targets
        - Testability requirements
        - Include specific maintainability metrics
        - Consider schema normalization approach
    """
    if "observability" in nfrlist:
        formatted_template += """
    h. Observability:
        - Logging requirements and log levels
        - Metrics collection and dashboarding
        - Distributed tracing requirements
        - Alerting thresholds and policies
        - Health check endpoints
        - Include specific observability tools and standards
        - Consider monitoring for potential failure points
    """
    if "infra_cost" in nfrlist:
        formatted_template += """
    i. Cost Efficiency:
        - Infrastructure cost targets
        - Resource optimization requirements
        - Cost allocation and tracking
        - Efficiency metrics
        - Include specific cost targets and optimization strategies
        - Consider database archival policies
    """
    if "data_management" in nfrlist:
        formatted_template += """
    j. Data Management:
        - Data volume projections
        - Data retention policies
        - Backup and recovery requirements
        - Data archiving strategies
        - Include specific data management metrics and policies
        - Address ACID requirements
        - Consider join complexity
        - Address data archival policies
    """

    formatted_template += """
    3. For EACH NFR category:
    - Provide specific, measurable criteria
    - Include exact threshold values and metrics
    - Specify testing and validation methodologies
    - Document monitoring approaches
    - Detail mitigation strategies for potential shortfalls

    4. Include a comprehensive NFR traceability matrix showing:
    - How each NFR relates to business requirements
    - Which components are responsible for meeting each NFR
    - How each NFR will be validated and measured
    - Priority level for each NFR

    5. The entire section must:
    - Use precise technical terminology consistent with the domain
    - Include specific metrics rather than vague statements
    - Use tables to present thresholds, targets, and acceptance criteria
    - Maintain a clear connection to business requirements and technical constraints

    IMPORTANT: 
    - Derive all necessary information from the problem statement, business context, and database information provided
    - Only include subsections for NFR categories that are relevant based on the project requirements
    - Use tables for presenting metrics, thresholds, and targets
    - Use bullet points and numbered lists for clarity and readability
    - Include specific, measurable criteria wherever possible

    Write the Non-Functional Requirements (NFRs) section with appropriate subsections for each relevant NFR category, including specific metrics and acceptance criteria. 
    """

    return formatted_template