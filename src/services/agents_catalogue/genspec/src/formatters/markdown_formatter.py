"""
Markdown formatter for specification outputs.
"""

from typing import Dict, Any, List
import os
import re
import uuid
import subprocess
import tempfile
from src.services.agents_catalogue.genspec.src.formatters.formatter import BaseFormatter


class MarkdownFormatter(BaseFormatter):
    """
    Formatter for Markdown output.
    """
    
    def __init__(self):
        """
        Initialize the Markdown formatter.
        """
        pass
    
    def format(self, spec_data: Dict[str, Any], **kwargs) -> str:
        """
        Format the specification data into Markdown.
        
        Args:
            spec_data: The specification data to format
            **kwargs: Additional formatter-specific arguments
            
        Returns:
            Markdown formatted specification as a string
        """
        output = []
        
        # Add title
        title = spec_data.get("title", "Technical Specification")
        output.append(f"# {title}\n")
        
        # Add metadata if available
        if "metadata" in spec_data:
            output.append("## Metadata\n")
            for key, value in spec_data["metadata"].items():
                output.append(f"- **{key}:** {value}")
            output.append("\n")
        
        # Add table of contents
        output.append("## Table of Contents\n")
        for i, section in enumerate(spec_data.get("sections", []), 1):
            section_title = section.get("title", f"Section {i}")
            anchor = self._create_anchor(section_title)
            output.append(f"{i}. [{section_title}](#{anchor})")
        output.append("\n")
        
        # Add sections
        for section in spec_data.get("sections", []):
            self._format_section(section, output)
        
        markdown_content = "\n".join(output)
        
        # Check if we should render Mermaid diagrams
        render_mermaid = kwargs.get("render_mermaid", False)
        if render_mermaid:
            try:
                markdown_content = self._convert_mermaid_to_images(markdown_content, kwargs.get("output_dir", "./"))
            except Exception as e:
                print(f"Warning: Failed to convert Mermaid diagrams to images: {str(e)}")
        
        return markdown_content
    
    def _convert_mermaid_to_images(self, markdown_content: str, output_dir: str) -> str:
        """
        Convert Mermaid code blocks to images.
        
        Args:
            markdown_content: The markdown content containing Mermaid code blocks
            output_dir: Directory to save the generated images
            
        Returns:
            Markdown content with Mermaid code blocks replaced by image references
        """
        # Create images directory if it doesn't exist
        images_dir = os.path.join(output_dir, "images")
        os.makedirs(images_dir, exist_ok=True)
        
        # Find all Mermaid code blocks
        pattern = r"```mermaid\n([\s\S]*?)\n```"
        
        def replace_mermaid(match):
            mermaid_code = match.group(1)
            
            # Generate a unique filename
            filename = f"mermaid_{uuid.uuid4().hex[:8]}.png"
            output_path = os.path.join(images_dir, filename)
            
            # Save Mermaid code to temporary file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.mmd', delete=False) as temp:
                temp.write(mermaid_code)
                temp_path = temp.name
            
            try:
                # Check if mmdc (Mermaid CLI) is installed
                try:
                    # Try to use mmdc (Mermaid CLI) if available
                    subprocess.run(
                        ["mmdc", "-i", temp_path, "-o", output_path, "-b", "transparent"],
                        check=True,
                        capture_output=True
                    )
                    return f"![Mermaid Diagram](images/{filename})"
                except (subprocess.SubprocessError, FileNotFoundError):
                    # If mmdc is not available, provide instructions
                    print("Mermaid CLI not found. To render Mermaid diagrams, install it with: npm install -g @mermaid-js/mermaid-cli")
                    # Keep the original Mermaid code block
                    return match.group(0)
            finally:
                # Clean up temporary file
                try:
                    os.unlink(temp_path)
                except:
                    pass
        
        # Replace Mermaid code blocks with image references
        return re.sub(pattern, replace_mermaid, markdown_content)
    
    def _format_section(self, section: Dict[str, Any], output: List[str]):
        """
        Format a section into Markdown.
        
        Args:
            section: The section data
            output: The output list to append to
        """
        title = section.get("title", "Untitled Section")
        content = section.get("content", "")
        
        # Add section title
        output.append(f"## {title}\n")
        
        # Check if this is an architecture section with image metadata
        if "metadata" in section and "architecture_image" in section["metadata"]:
            # Process architecture image
            image_data = section["metadata"]["architecture_image"]
            image_path = image_data.get("image_file_path", "")
            
            # Replace the image reference in content if needed
            if "![Architecture Diagram]" in content and image_path:
                # Make sure the image path is relative if possible
                relative_path = self._make_path_relative(image_path)
                content = content.replace(f"![Architecture Diagram]({image_path})", 
                                         f"![Architecture Diagram]({relative_path})")
        
        # Add section content
        output.append(content)
        
        # Add subsections if any
        for subsection in section.get("subsections", []):
            self._format_subsection(subsection, output)
        
        output.append("\n")
    
    def _make_path_relative(self, path: str) -> str:
        """
        Convert an absolute path to a relative path if possible.
        
        Args:
            path: The file path
            
        Returns:
            Relative path if possible, otherwise the original path
        """
        # If it's already a relative path, return as is
        if not os.path.isabs(path):
            return path
            
        # Try to make it relative to the current directory
        try:
            return os.path.relpath(path)
        except:
            # If that fails, return the original path
            return path
    
    def _format_subsection(self, subsection: Dict[str, Any], output: List[str]):
        """
        Format a subsection into Markdown.
        
        Args:
            subsection: The subsection data
            output: The output list to append to
        """
        title = subsection.get("title", "Untitled Subsection")
        content = subsection.get("content", "")
        
        # Add subsection title
        output.append(f"### {title}\n")
        
        # Add subsection content
        output.append(content)
        output.append("\n")
    
    def _create_anchor(self, title: str) -> str:
        """
        Create an anchor from a title.
        
        Args:
            title: The section title
            
        Returns:
            Anchor string for the title
        """
        # Convert to lowercase and replace spaces with hyphens
        anchor = title.lower().replace(" ", "-")
        # Remove any non-alphanumeric characters except hyphens
        anchor = "".join(c for c in anchor if c.isalnum() or c == "-")
        return anchor
    
    def get_extension(self) -> str:
        """
        Get the file extension for Markdown output.
        
        Returns:
            File extension "md"
        """
        return "md" 