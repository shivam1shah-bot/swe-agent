"""
Approach evaluator service.
"""

from typing import Dict, Any, List

from src.services.agents_catalogue.genspec.src.services.client_factory import get_client_class
from src.services.agents_catalogue.genspec.src.services.langchain_manager import LangChainManager
from src.providers.logger import Logger
from src.api.dependencies import get_logger
logger = get_logger("approach-evaluator")

class ApproachEvaluator:
    """
    Evaluates different implementation approaches and provides recommendations.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the approach evaluator.
        
        Args:
            config: Configuration dictionary
        """
        self.config = config
        ClientClass = get_client_class(config["provider"])
        self.bedrock_client = ClientClass(config)
        self.langchain_manager = LangChainManager(config)
        self.prompt_template_path = config["analysis"]["approach_evaluation_prompt_template"]
# Deleted unused prompt_template_path attribute
        logger.info("Initialized approach evaluator")
    
    def evaluate(self, spec_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Evaluate different implementation approaches and provide recommendations.
        
        Args:
            spec_data: Specification data collected so far
            
        Returns:
            Dictionary containing approach evaluations and recommendations
        """
        try:
            # Extract relevant information from spec_data
            problem_statement = spec_data.get("problem_statement", "")
            introduction = spec_data.get("introduction", "")
            scope = spec_data.get("scope", "")
            goals = spec_data.get("goals", [])
            
            # Format goals as a string
            goals_text = "\n".join([f"- {goal}" for goal in goals]) if goals else "No specific goals provided."
            
            # Combine all available information for analysis
            combined_input = f"""
            PROBLEM STATEMENT:
            {problem_statement}
            
            INTRODUCTION:
            {introduction}
            
            SCOPE:
            {scope}
            
            GOALS:
            {goals_text}
            """
            
            # Add architecture information if available
            if "current_architecture_description" in spec_data:
                combined_input += f"\nCURRENT ARCHITECTURE:\n{spec_data['current_architecture_description']}"
            
            if "components" in spec_data:
                components_text = "\n".join(spec_data["components"])
                combined_input += f"\nCOMPONENTS:\n{components_text}"
            
            # Add database information if available
            if "database_changes" in spec_data:
                combined_input += f"\nDATABASE INFORMATION:\n{spec_data['database_changes']}"
            
            # Add resilience information if available
            if "reliability" in spec_data:
                combined_input += f"\nRELIABILITY REQUIREMENTS:\n{spec_data['reliability']}"
            
            # Create system prompt for approach evaluation
            system_prompt = self._get_system_prompt()
            
            # Generate the analysis using Bedrock
            analysis_result = self.bedrock_client.generate_text(
                prompt=combined_input,
                system_prompt=system_prompt
            )
            
            # Parse the result into structured data
            approach_evaluation = self._parse_analysis_result(analysis_result)
            
            logger.info("Approach evaluation completed")
            return approach_evaluation
        except Exception as e:
            logger.error(f"Error evaluating approaches: {str(e)}")
            raise
    
    def _get_system_prompt(self) -> str:
        """
        Get the system prompt for approach evaluation.
        
        Returns:
            System prompt string
        """
        return """
        You are a senior software architect with expertise in system design, architecture evaluation, and implementation planning.
        
        Based on the provided requirements and information, generate and evaluate multiple implementation approaches.
        
        Your analysis should include:
        
        1. APPROACHES: Generate 2-3 distinct implementation approaches, each with:
           - A clear name
           - A detailed description
           - A list of pros and cons
           - A Mermaid diagram illustrating the approach (MUST use 'flowchart TD' syntax, NOT 'graph TD')
           - Implementation timeline estimates
        
        2. SELECTED_APPROACH: Recommend the best approach with justification
        
        3. BUSINESS_LOGIC_CHANGES: Detail the business logic changes required
        
        4. SCALABILITY: Analyze scalability considerations
        
        5. AVAILABILITY: Analyze availability considerations
        
        6. SECURITY: Analyze security considerations
        
        7. COMPLIANCE: Analyze compliance considerations
        
        8. INFRA_COST: Estimate infrastructure costs
        
        9. TESTING_PLAN: Provide a comprehensive testing plan
        
        10. GO_LIVE_PLAN: Provide a go-live plan including:
            - Rollout strategy
            - Backward compatibility considerations
            - Rollback plan
        
        11. DEPENDENCIES: List external dependencies with owners and SLAs
        
        12. MILESTONES: Provide key implementation milestones with estimated completion dates
        
        CRITICAL MERMAID REQUIREMENTS:
        - Use 'flowchart TD' for architecture diagrams (NOT 'graph TD')
        - Apply professional styling with classDef and class assignments
        - Use proper node shapes: [Service], (API), [(Database)], ((External))
        - Use professional colors: blues #3498db #2980b9, greens #27ae60 #16a085, grays #95a5a6 #7f8c8d
        
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
            "APPROACHES": "approaches_raw",
            "SELECTED_APPROACH": "selected_approach_raw",
            "BUSINESS_LOGIC_CHANGES": "business_logic_changes",
            "SCALABILITY": "scalability",
            "AVAILABILITY": "availability",
            "SECURITY": "security",
            "COMPLIANCE": "compliance",
            "INFRA_COST": "infra_cost",
            "TESTING_PLAN": "testing_plan",
            "GO_LIVE_PLAN": "go_live_plan_raw",
            "DEPENDENCIES": "dependencies_raw",
            "MILESTONES": "milestones_raw"
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
        
        # Process the raw sections into structured data
        parsed_data["evaluated_approaches"] = self._parse_approaches(parsed_data.get("approaches_raw", ""))
        parsed_data["selected_approach"] = self._parse_selected_approach(parsed_data.get("selected_approach_raw", ""))
        parsed_data["go_live_plan"], parsed_data["rollout_plan"], parsed_data["backward_compatibility"], parsed_data["rollback_plan"] = self._parse_go_live_plan(parsed_data.get("go_live_plan_raw", ""))
        parsed_data["dependencies"] = self._parse_dependencies(parsed_data.get("dependencies_raw", ""))
        parsed_data["milestones"] = self._parse_milestones(parsed_data.get("milestones_raw", ""))
        
        return parsed_data
    
    def _parse_approaches(self, approaches_text: str) -> List[Dict[str, Any]]:
        """
        Parse the approaches section into structured data.
        
        Args:
            approaches_text: Raw approaches text
            
        Returns:
            List of approach dictionaries
        """
        if not approaches_text:
            return []
        
        approaches = []
        current_approach = None
        current_section = None
        section_content = []
        
        # Split by lines and process
        lines = approaches_text.split('\n')
        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue
            
            # Check if this is a new approach header (Approach 1, Approach 2, etc.)
            if line.lower().startswith(("approach 1", "approach 2", "approach 3")):
                # Save previous approach if exists
                if current_approach:
                    if current_section and section_content:
                        current_approach[current_section] = "\n".join(section_content)
                    approaches.append(current_approach)
                
                # Start new approach
                current_approach = {
                    "name": line.split(":", 1)[1].strip() if ":" in line else line,
                    "description": "",
                    "pros": [],
                    "cons": [],
                    "diagram": "",
                    "timeline": ""
                }
                current_section = "description"
                section_content = []
                continue
            
            # Check for sections within an approach
            if line.lower() == "pros:" or line.lower().startswith("pros:"):
                if current_approach and current_section and section_content:
                    current_approach[current_section] = "\n".join(section_content)
                current_section = "pros"
                section_content = []
                continue
            elif line.lower() == "cons:" or line.lower().startswith("cons:"):
                if current_approach and current_section and section_content:
                    current_approach[current_section] = "\n".join(section_content)
                current_section = "cons"
                section_content = []
                continue
            elif line.lower().startswith(("diagram:", "mermaid diagram:")):
                if current_approach and current_section and section_content:
                    current_approach[current_section] = "\n".join(section_content)
                current_section = "diagram"
                section_content = []
                continue
            elif line.lower().startswith(("timeline:", "implementation timeline:")):
                if current_approach and current_section and section_content:
                    current_approach[current_section] = "\n".join(section_content)
                current_section = "timeline"
                section_content = []
                continue
            
            # Add content to current section
            if current_approach and current_section:
                # For pros and cons, parse list items
                if current_section in ["pros", "cons"] and (line.startswith("- ") or line.startswith("* ")):
                    current_approach[current_section].append(line[2:].strip())
                else:
                    section_content.append(line)
        
        # Don't forget to add the last approach
        if current_approach:
            if current_section and section_content:
                current_approach[current_section] = "\n".join(section_content)
            approaches.append(current_approach)
        
        return approaches
    
    def _parse_selected_approach(self, selected_approach_text: str) -> Dict[str, str]:
        """
        Parse the selected approach section.
        
        Args:
            selected_approach_text: Raw selected approach text
            
        Returns:
            Dictionary with selected approach information
        """
        lines = selected_approach_text.split('\n')
        name = lines[0] if lines else "No approach selected"
        justification = "\n".join(lines[1:]) if len(lines) > 1 else ""
        
        return {
            "name": name,
            "justification": justification
        }
    
    def _parse_go_live_plan(self, go_live_text: str) -> tuple:
        """
        Parse the go-live plan section.
        
        Args:
            go_live_text: Raw go-live plan text
            
        Returns:
            Tuple of (go_live_plan, rollout_plan, backward_compatibility, rollback_plan)
        """
        go_live_plan = go_live_text
        rollout_plan = ""
        backward_compatibility = ""
        rollback_plan = ""
        
        # Try to extract subsections
        sections = {
            "rollout plan": "rollout_plan",
            "backward compatibility": "backward_compatibility",
            "rollback plan": "rollback_plan"
        }
        
        current_section = "go_live_plan"
        section_content = []
        
        for line in go_live_text.split('\n'):
            line = line.strip()
            if not line:
                continue
            
            found_section = False
            for marker, key in sections.items():
                if line.lower().startswith(marker) or line.lower() == marker:
                    # Save previous section
                    if current_section == "go_live_plan":
                        go_live_plan = "\n".join(section_content)
                    elif current_section == "rollout_plan":
                        rollout_plan = "\n".join(section_content)
                    elif current_section == "backward_compatibility":
                        backward_compatibility = "\n".join(section_content)
                    elif current_section == "rollback_plan":
                        rollback_plan = "\n".join(section_content)
                    
                    # Start new section
                    current_section = key
                    section_content = []
                    found_section = True
                    break
            
            if not found_section:
                section_content.append(line)
        
        # Save the last section
        if current_section == "go_live_plan":
            go_live_plan = "\n".join(section_content)
        elif current_section == "rollout_plan":
            rollout_plan = "\n".join(section_content)
        elif current_section == "backward_compatibility":
            backward_compatibility = "\n".join(section_content)
        elif current_section == "rollback_plan":
            rollback_plan = "\n".join(section_content)
        
        return go_live_plan, rollout_plan, backward_compatibility, rollback_plan
    
    def _parse_dependencies(self, dependencies_text: str) -> List[Dict[str, str]]:
        """
        Parse the dependencies section.
        
        Args:
            dependencies_text: Raw dependencies text
            
        Returns:
            List of dependency dictionaries
        """
        dependencies = []
        
        # Look for table format or list format
        if "|" in dependencies_text:  # Table format
            rows = [row.strip() for row in dependencies_text.split('\n') if row.strip()]
            
            # Skip header and separator rows
            data_rows = [row for row in rows if not row.startswith('|--') and not row.startswith('+-')]
            
            for row in data_rows:
                if not row.startswith('|'):
                    continue
                    
                cells = [cell.strip() for cell in row.split('|')[1:-1]]
                if len(cells) >= 3:
                    dependencies.append({
                        "name": cells[0],
                        "owner": cells[1] if len(cells) > 1 else "N/A",
                        "sla": cells[2] if len(cells) > 2 else "N/A",
                        "notes": cells[3] if len(cells) > 3 else ""
                    })
        else:  # List format
            for line in dependencies_text.split('\n'):
                line = line.strip()
                if line.startswith("- ") or line.startswith("* "):
                    parts = line[2:].split(":", 1)
                    name = parts[0].strip()
                    details = parts[1].strip() if len(parts) > 1 else ""
                    
                    dependencies.append({
                        "name": name,
                        "owner": "N/A",
                        "sla": "N/A",
                        "notes": details
                    })
        
        return dependencies
    
    def _parse_milestones(self, milestones_text: str) -> List[Dict[str, str]]:
        """
        Parse the milestones section.
        
        Args:
            milestones_text: Raw milestones text
            
        Returns:
            List of milestone dictionaries
        """
        milestones = []
        
        # Look for table format or list format
        if "|" in milestones_text:  # Table format
            rows = [row.strip() for row in milestones_text.split('\n') if row.strip()]
            
            # Skip header and separator rows
            data_rows = [row for row in rows if not row.startswith('|--') and not row.startswith('+-')]
            
            for row in data_rows:
                if not row.startswith('|'):
                    continue
                    
                cells = [cell.strip() for cell in row.split('|')[1:-1]]
                if len(cells) >= 2:
                    milestones.append({
                        "name": cells[0],
                        "completion_date": cells[1] if len(cells) > 1 else "TBD",
                        "owner": cells[2] if len(cells) > 2 else "TBD"
                    })
        else:  # List format
            for line in milestones_text.split('\n'):
                line = line.strip()
                if line.startswith("- ") or line.startswith("* "):
                    parts = line[2:].split(":", 1)
                    name = parts[0].strip()
                    details = parts[1].strip() if len(parts) > 1 else ""
                    
                    milestones.append({
                        "name": name,
                        "completion_date": "TBD",
                        "owner": "TBD"
                    })
        
        return milestones 