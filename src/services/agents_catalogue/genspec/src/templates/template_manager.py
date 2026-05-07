"""
Template manager for handling specification templates.
"""

import os
from typing import Dict, Any
from datetime import datetime
import jinja2
from src.providers.logger import Logger
from src.api.dependencies import get_logger
from src.services.agents_catalogue.genspec.src.services.client_factory import get_client_class
logger = get_logger("template-manager")

class TemplateManager:
    """
    Manages templates for generating technical specifications.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the template manager.
        
        Args:
            config: Configuration dictionary
        """
        self.config = config
        self.base_dir = config["templates"]["base_dir"]
        ClientClass = get_client_class(config["provider"])
        self.bedrock_client = ClientClass(config)
        
        # Set up Jinja2 environment
        self.env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(self.base_dir),
            autoescape=jinja2.select_autoescape(['html', 'xml']),
            trim_blocks=True,
            lstrip_blocks=True
        )
        
        # Add custom filters
        self.env.filters['date'] = lambda d: d.strftime('%Y-%m-%d')
        
        # Define section prompt paths - now with numbered files
        self.section_prompts = {
            "problem_statement": os.path.join("src/prompts_for_sections/sections/1_problem_statement.txt"),
            "introduction": os.path.join("src/prompts_for_sections/sections/2_introduction.txt"),
            "scope": os.path.join("src/prompts_for_sections/sections/2_1_scope.txt"),
            "out_of_scope": os.path.join("src/prompts_for_sections/sections/3_out_of_scope.txt"),
            "futuristic_scope": os.path.join("src/prompts_for_sections/sections/4_futuristic_scope.txt"),
            "assumptions_goals": os.path.join("src/prompts_for_sections/sections/5_assumptions_goals.txt"),
            "current_architecture": os.path.join("src/prompts_for_sections/sections/6_current_architecture.txt"),
            "evaluated_approaches": os.path.join("src/prompts_for_sections/sections/7_evaluated_approaches.txt"),
            "data_model_changes": os.path.join("src/prompts_for_sections/sections/7_2_data_model_changes.txt"),
            "business_logic_changes": os.path.join("src/prompts_for_sections/sections/7_3_business_logic_changes.txt"),
            "db_evaluation": os.path.join("src/prompts_for_sections/sections/7_4_db_evaluation.txt"),
            "nfr": os.path.join("src/prompts_for_sections/sections/8_nfr.txt"),
            "dependencies": os.path.join("src/prompts_for_sections/sections/9_dependencies.txt"),
            "testing_plan": os.path.join("src/prompts_for_sections/sections/10_testing_plan.txt"),
            "go_live_plan": os.path.join("src/prompts_for_sections/sections/11_go_live_plan.txt"),
            "monitoring_logging": os.path.join("src/prompts_for_sections/sections/12_monitoring_logging.txt"),
            "milestones_timelines": os.path.join("src/prompts_for_sections/sections/13_milestones_timelines.txt"),
        }
        
        logger.info(f"Initialized template manager with base directory: {self.base_dir}")
    
    def generate_specification(self, template_name: str, data: Dict[str, Any], output_dir: str) -> str:
        """
        Generate a technical specification using the specified template.
        
        Args:
            template_name: Name of the template to use
            data: Data to populate the template
            output_dir: Directory to save the generated specification
            
        Returns:
            Path to the generated specification file
        """
        try:
            # Get the template
            template_path = self._get_template_path(template_name)
            template = self.env.get_template(os.path.basename(template_path))
            
            # Add standard context variables
            context = {
                'current_date': datetime.now(),
                'author': data.get('author', 'Tech-SpecGen'),
                'project_name': data.get('project_name', 'Untitled Project'),
                'version': '1.0',
                'status': 'Draft',
                **data
            }
            
            # Generate section content using LLM
            enhanced_context = self._generate_section_content(context)
            
            # Render the template
            rendered_content = template.render(**enhanced_context)
            
            # Save the rendered content
            output_filename = f"{enhanced_context['project_name'].replace(' ', '_').lower()}_technical_specification.md"
            output_path = os.path.join(output_dir, output_filename)
            
            with open(output_path, 'w') as file:
                file.write(rendered_content)
            
            logger.info(f"Generated specification: {output_path}")
            return output_path
        except Exception as e:
            logger.error(f"Error generating specification: {str(e)}")
            raise
    
    def _get_template_path(self, template_name: str) -> str:
        """
        Get the path to the specified template.
        
        Args:
            template_name: Name of the template
            
        Returns:
            Path to the template file
        """
        if template_name == "default":
            template_path = os.path.join(self.base_dir, self.config["templates"]["default"])
        else:
            template_path = os.path.join(self.base_dir, f"{template_name}.md")
        
        if not os.path.exists(template_path):
            logger.warning(f"Template not found: {template_path}")
            logger.info("Using default template")
            template_path = os.path.join(self.base_dir, self.config["templates"]["default"])
        
        return template_path
    
    def _generate_section_content(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate enhanced content for each section using LLM.
        
        Args:
            data: Data to use for generating section content
            
        Returns:
            Enhanced data dictionary with generated section content
        """
        enhanced_data = data.copy()
        
        # Process each section if the prompt file exists
        for section_name, prompt_path in self.section_prompts.items():
            if os.path.exists(prompt_path):
                logger.info(f"Generating content for section: {section_name}")
                
                try:
                    # Read the prompt template
                    with open(prompt_path, 'r') as file:
                        prompt_template = file.read()
                    
                    # Format the prompt with data
                    formatted_prompt = self._format_prompt(prompt_template, data)
                    
                    # Generate content using LLM
                    section_content = self.bedrock_client.generate_text(formatted_prompt)
                    
                    # Add the generated content to the enhanced data
                    enhanced_data[f"generated_{section_name}"] = section_content
                    
                except Exception as e:
                    logger.error(f"Error generating content for section {section_name}: {str(e)}")
                    enhanced_data[f"generated_{section_name}"] = f"Error generating content: {str(e)}"
        
        return enhanced_data
    
    def _format_prompt(self, prompt_template: str, data: Dict[str, Any]) -> str:
        """
        Format a prompt template with data.
        
        Args:
            prompt_template: Prompt template string
            data: Data to use for formatting
            
        Returns:
            Formatted prompt string
        """
        # Simple string formatting for placeholders in the prompt
        formatted_prompt = prompt_template
        
        for key, value in data.items():
            placeholder = f"{{{key}}}"
            if placeholder in formatted_prompt:
                # Convert value to string representation
                if isinstance(value, list):
                    str_value = "\n".join([f"- {item}" for item in value])
                elif isinstance(value, dict):
                    str_value = "\n".join([f"{k}: {v}" for k, v in value.items()])
                else:
                    str_value = str(value)
                
                formatted_prompt = formatted_prompt.replace(placeholder, str_value)
        
        return formatted_prompt 