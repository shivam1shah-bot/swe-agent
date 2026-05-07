"""
Parser for Product Requirements Documents (PRDs).
"""

import re
import base64
from typing import Dict, Any, List
from src.services.agents_catalogue.genspec.src.parsers.base_parser import BaseParser


class PRDParser(BaseParser):
    """
    Parser for Product Requirements Documents (PRDs).
    """
    
    def __init__(self):
        """
        Initialize the PRD parser.
        """
        # Common section headers in PRDs
        self.section_patterns = {
            "overview": r"(overview|introduction|summary|How will we announce this offering to the world)",
            "problem_statement": r"(problem statement|problem definition|problem|challenge|What problem are we solving)",
            "current_architechture": r"(current architecture|current system|current system architecture|current system design|current system overview|architecture|system architecture)",
            "goals": r"(goals|objectives|aims|purpose)",
            "non_goals": r"(non[\s-]*goals|out of scope)",
            "user_stories": r"(user stories|use cases|scenarios)",
            "requirements": r"(requirements|features|functionality)",
            "functional_requirements": r"(functional requirements|features|functionality|What would a 1-page press-release look like)",
            "non_functional_requirements": r"(non[\s-]*functional requirements|nfrs|constraints)",
            "assumptions": r"(assumptions|prerequisites|dependencies)",
            "metrics": r"(metrics|success criteria|kpis)",
            "timeline": r"(timeline|schedule|milestones|roadmap)",
            "risks": r"(risks|challenges|considerations)"
        }
        
        # Regex for requirement identifiers
        self.req_id_pattern = r"(REQ|FR|NFR|UR)-\d+"
    
    def validate(self, content: str) -> bool:
        """
        Validate if the content appears to be a PRD.
        
        Args:
            content: The content to validate
            
        Returns:
            True if the content appears to be a PRD, False otherwise
        """
        # Check if content contains common PRD section headers
        content = content.strip()
        section_count = 0
        
        for pattern in self.section_patterns.values():
            if re.search(pattern, content, re.MULTILINE):
                section_count += 1
        
        # If we find at least 3 common PRD sections, consider it a PRD
        return section_count >= 3
    
    def parse(self, content: str, images: List[Dict[str, Any]] = None, **kwargs) -> Dict[str, Any]:
        """
        Parse a PRD and extract structured information.
        
        Args:
            content: The PRD content
            images: List of images extracted from the document
            **kwargs: Additional parser-specific arguments
            
        Returns:
            Dictionary containing the parsed PRD data
        """
        result = {
            "type": "prd",
            "content": content,
            "sections": {}
        }
        # Determine document type
        is_markdown = self._is_markdown(content)

        # Extract title
        if is_markdown:
            title_match = re.search(r"(?i)^#\s+(.+?)$", content, re.MULTILINE)
        else:
            title_match = re.search(r"^(.+?)\n", content)
        
        if title_match:
            result["title"] = title_match.group(1).strip()
        else:
            result["title"] = "Untitled PRD"
        
        # Extract sections
        for section_name, pattern in self.section_patterns.items():
            section_content = self._extract_section(content, pattern, is_markdown)
            if section_content:
                result["sections"][section_name] = section_content

                
       
        # Extract requirements
        result["requirements"] = self._extract_requirements(content)
        
        # Extract user stories
        result["user_stories"] = self._extract_user_stories(content)
        
        return result
    
    def _extract_section(self, content: str, pattern: str, is_markdown: bool) -> str:
        """
        Extract a section from the PRD based on a pattern.
        
        Args:
            content: The PRD content
            pattern: The regex pattern for the section header
            
        Returns:
            The section content or empty string if not found
        """
        # Look for section header with markdown heading syntax (# or ## or ### etc.)
        # Adjust the pattern to allow optional numbering before the section title
        if is_markdown:
            header_match = re.search(r"^(#{1,6})\s*(\d+\\?\.\s*)?" + pattern + r"[:\s]*(.*)$", content, re.MULTILINE | re.IGNORECASE)
        else:
            header_match = re.search(r"^(\d+\.\d*)\s+" + pattern + r"[:\s]*(.*)$", content, re.MULTILINE | re.IGNORECASE)
        
        if header_match:
            heading_level = len(header_match.group(1))
            section_start = header_match.start()
            
            # Find the next heading of the same or higher level
            if is_markdown:
                next_heading_pattern = r"^#{1," + str(heading_level) + r"}\s"
            else:
                next_heading_pattern = r"^\d+\.\d*\s"

            next_heading_match = re.search(next_heading_pattern, content[section_start + 1:], re.MULTILINE)
            
            if next_heading_match:
                section_end = section_start + 1 + next_heading_match.start()
                section_content = content[section_start:section_end].strip()
            else:
                section_content = content[section_start:].strip()
            
            # Remove the header itself
            header_end = content.find("\n", section_start)
            if header_end != -1:
                section_content = section_content[header_end - section_start:].strip()
            
            return section_content
        
        return ""
    
    def _extract_requirements(self, content: str) -> List[Dict[str, str]]:
        """
        Extract requirements from the PRD.
        
        Args:
            content: The PRD content
            
        Returns:
            List of requirement dictionaries
        """
        requirements = []

        is_markdown = self._is_markdown(content)
        
        # Try to find requirements with IDs
        req_pattern = r"(?i)(" + self.req_id_pattern + r")\s*[:\-]\s*(.+?)(?=\n\n|\n" + self.req_id_pattern + r"|\Z)"
        for match in re.finditer(req_pattern, content, re.DOTALL):
            req_id = match.group(1)
            req_text = match.group(2).strip()
            
            requirements.append({
                "id": req_id,
                "text": req_text,
                "type": self._determine_requirement_type(req_id)
            })
        
        # If no requirements with IDs found, try to find bullet points in requirements section
        if not requirements:
            req_section = self._extract_section(content, self.section_patterns["requirements"], is_markdown)
            if req_section:
                bullet_pattern = r"(?:^|\n)[-*•]\s+(.+?)(?=\n[-*•]|\Z)"
                for i, match in enumerate(re.finditer(bullet_pattern, req_section, re.DOTALL)):
                    req_text = match.group(1).strip()
                    requirements.append({
                        "id": f"REQ-{i+1:03d}",
                        "text": req_text,
                        "type": "functional"
                    })
        
        return requirements
    
    def _determine_requirement_type(self, req_id: str) -> str:
        """
        Determine the type of requirement based on its ID.
        
        Args:
            req_id: The requirement ID
            
        Returns:
            The requirement type
        """
        req_id = req_id.upper()
        if req_id.startswith("FR"):
            return "functional"
        elif req_id.startswith("NFR"):
            return "non-functional"
        elif req_id.startswith("UR"):
            return "user"
        return "general"
    
    def _extract_user_stories(self, content: str) -> List[Dict[str, str]]:
        """
        Extract user stories from the PRD.
        
        Args:
            content: The PRD content
            
        Returns:
            List of user story dictionaries
        """
        user_stories = []
        is_markdown = self._is_markdown(content)
        
        # Extract user stories section
        user_stories_section = self._extract_section(content, self.section_patterns["user_stories"], is_markdown)
        if not user_stories_section:
            return user_stories
        
        # Look for standard user story format: "As a [role], I want [goal], so that [benefit]"
        story_pattern = r"(?i)As\s+a\s+([^,\.]+),\s+I\s+want\s+([^,\.]+),\s+so\s+that\s+([^,\.]+)"
        for i, match in enumerate(re.finditer(story_pattern, user_stories_section)):
            role = match.group(1).strip()
            goal = match.group(2).strip()
            benefit = match.group(3).strip()
            
            user_stories.append({
                "id": f"US-{i+1:03d}",
                "role": role,
                "goal": goal,
                "benefit": benefit,
                "text": f"As a {role}, I want {goal}, so that {benefit}"
            })
        
        # If no standard format found, look for bullet points
        if not user_stories:
            bullet_pattern = r"(?:^|\n)[-*•]\s+(.+?)(?=\n[-*•]|\Z)"
            for i, match in enumerate(re.finditer(bullet_pattern, user_stories_section, re.DOTALL)):
                story_text = match.group(1).strip()
                
                # Try to parse as user story format
                story_match = re.search(story_pattern, story_text)
                if story_match:
                    role = story_match.group(1).strip()
                    goal = story_match.group(2).strip()
                    benefit = story_match.group(3).strip()
                    
                    user_stories.append({
                        "id": f"US-{i+1:03d}",
                        "role": role,
                        "goal": goal,
                        "benefit": benefit,
                        "text": story_text
                    })
                else:
                    # Just add as plain text
                    user_stories.append({
                        "id": f"US-{i+1:03d}",
                        "text": story_text
                    })
        
        return user_stories 

    def _is_markdown(self, content: str) -> bool:
        """
        Determine if the document is in Markdown format.
        
        Args:
            content: The document content.
        
        Returns:
            True if the document is Markdown, False otherwise.
        """
        # Simple heuristic: check for Markdown heading syntax
        return bool(re.search(r"^#\s+", content, re.MULTILINE))