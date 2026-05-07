"""
HTML formatter for specification outputs.
"""

from typing import Dict, Any, List
import html
import os
from src.services.agents_catalogue.genspec.src.formatters.formatter import BaseFormatter


class HTMLFormatter(BaseFormatter):
    """
    Formatter for HTML output.
    """
    
    def __init__(self):
        """
        Initialize the HTML formatter.
        """
        pass
    
    def format(self, spec_data: Dict[str, Any], **kwargs) -> str:
        """
        Format the specification data into HTML.
        
        Args:
            spec_data: The specification data to format
            **kwargs: Additional formatter-specific arguments
            
        Returns:
            HTML formatted specification as a string
        """
        title = spec_data.get("title", "Technical Specification")
        
        # Start building HTML
        output = []
        output.append("<!DOCTYPE html>")
        output.append("<html lang=\"en\">")
        output.append("<head>")
        output.append("    <meta charset=\"UTF-8\">")
        output.append("    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">")
        output.append(f"    <title>{html.escape(title)}</title>")
        output.append("    <style>")
        output.append("        body { font-family: Arial, sans-serif; line-height: 1.6; max-width: 900px; margin: 0 auto; padding: 20px; }")
        output.append("        h1 { color: #333; border-bottom: 2px solid #eee; padding-bottom: 10px; }")
        output.append("        h2 { color: #444; margin-top: 30px; border-bottom: 1px solid #eee; padding-bottom: 5px; }")
        output.append("        h3 { color: #555; }")
        output.append("        .metadata { background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin-bottom: 20px; }")
        output.append("        .metadata-item { margin: 5px 0; }")
        output.append("        .toc { background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin-bottom: 20px; }")
        output.append("        code { background-color: #f5f5f5; padding: 2px 5px; border-radius: 3px; font-family: monospace; }")
        output.append("        pre { background-color: #f5f5f5; padding: 15px; border-radius: 5px; overflow-x: auto; }")
        output.append("    </style>")
        output.append("</head>")
        output.append("<body>")
        
        # Title
        output.append(f"    <h1>{html.escape(title)}</h1>")
        
        # Metadata
        if "metadata" in spec_data:
            output.append("    <div class=\"metadata\">")
            output.append("        <h2>Metadata</h2>")
            for key, value in spec_data["metadata"].items():
                output.append(f"        <div class=\"metadata-item\"><strong>{html.escape(key)}:</strong> {html.escape(str(value))}</div>")
            output.append("    </div>")
        
        # Table of Contents
        output.append("    <div class=\"toc\">")
        output.append("        <h2>Table of Contents</h2>")
        output.append("        <ol>")
        for i, section in enumerate(spec_data.get("sections", []), 1):
            section_title = section.get("title", f"Section {i}")
            anchor = self._create_anchor(section_title)
            output.append(f"            <li><a href=\"#{anchor}\">{html.escape(section_title)}</a></li>")
        output.append("        </ol>")
        output.append("    </div>")
        
        # Sections
        for section in spec_data.get("sections", []):
            self._format_section(section, output)
        
        # Close HTML
        output.append("</body>")
        output.append("</html>")
        
        return "\n".join(output)
    
    def _format_section(self, section: Dict[str, Any], output: List[str]):
        """
        Format a section into HTML.
        
        Args:
            section: The section data
            output: The output list to append to
        """
        title = section.get("title", "Untitled Section")
        content = section.get("content", "")
        anchor = self._create_anchor(title)
        
        # Add section title
        output.append(f"    <h2 id=\"{anchor}\">{html.escape(title)}</h2>")
        
        # Check if this is an architecture section with image metadata
        if "metadata" in section and "architecture_image" in section["metadata"]:
            # Process architecture image
            image_data = section["metadata"]["architecture_image"]
            
            # Use data URI if available, otherwise use file path
            if "image_data_uri" in image_data and image_data["image_data_uri"]:
                data_uri = image_data["image_data_uri"]
                image_html = f'<div class="architecture-image"><img src="{data_uri}" alt="Architecture Diagram" style="max-width:100%;"></div>'
                
                # Replace the markdown image reference with HTML image tag
                if "![Architecture Diagram]" in content:
                    content = content.replace("![Architecture Diagram]", "")
                    # Remove the file path that follows
                    import re
                    content = re.sub(r'\(.*?\)', '', content)
                    # Add the HTML image
                    content += "\n\n" + image_html
            else:
                # Use file path
                image_path = image_data.get("image_file_path", "")
                if image_path:
                    # Make path relative if possible
                    relative_path = self._make_path_relative(image_path)
                    image_html = f'<div class="architecture-image"><img src="{html.escape(relative_path)}" alt="Architecture Diagram" style="max-width:100%;"></div>'
                    
                    # Replace the markdown image reference with HTML image tag
                    if "![Architecture Diagram]" in content:
                        content = content.replace("![Architecture Diagram]", "")
                        # Remove the file path that follows
                        import re
                        content = re.sub(r'\(.*?\)', '', content)
                        # Add the HTML image
                        content += "\n\n" + image_html
        
        # Add section content with markdown-to-html conversion
        output.append(f"    <div>{self._markdown_to_html(content)}</div>")
        
        # Add subsections if any
        for subsection in section.get("subsections", []):
            self._format_subsection(subsection, output)
    
    def _format_subsection(self, subsection: Dict[str, Any], output: List[str]):
        """
        Format a subsection into HTML.
        
        Args:
            subsection: The subsection data
            output: The output list to append to
        """
        title = subsection.get("title", "Untitled Subsection")
        content = subsection.get("content", "")
        anchor = self._create_anchor(title)
        
        # Add subsection title
        output.append(f"    <h3 id=\"{anchor}\">{html.escape(title)}</h3>")
        
        # Add subsection content with markdown-to-html conversion
        output.append(f"    <div>{self._markdown_to_html(content)}</div>")
    
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
    
    def _markdown_to_html(self, markdown_text: str) -> str:
        """
        Convert markdown text to HTML.
        This is a simple implementation and doesn't handle all markdown features.
        
        Args:
            markdown_text: The markdown text to convert
            
        Returns:
            HTML formatted text
        """
        # Handle code blocks
        markdown_text = self._convert_code_blocks(markdown_text)
        
        # Handle headers (h4, h5, h6 only since h1-h3 are handled separately)
        markdown_text = markdown_text.replace("\n#### ", "\n<h4>").replace(" ####\n", "</h4>\n")
        markdown_text = markdown_text.replace("\n##### ", "\n<h5>").replace(" #####\n", "</h5>\n")
        markdown_text = markdown_text.replace("\n###### ", "\n<h6>").replace(" ######\n", "</h6>\n")
        
        # Handle bold and italic
        markdown_text = markdown_text.replace("**", "<strong>").replace("**", "</strong>")
        markdown_text = markdown_text.replace("*", "<em>").replace("*", "</em>")
        
        # Handle lists
        lines = markdown_text.split("\n")
        in_list = False
        list_type = None
        result_lines = []
        
        for line in lines:
            if line.strip().startswith("- "):
                if not in_list or list_type != "ul":
                    if in_list:
                        result_lines.append(f"</{list_type}>")
                    result_lines.append("<ul>")
                    in_list = True
                    list_type = "ul"
                result_lines.append(f"<li>{html.escape(line.strip()[2:])}</li>")
            elif line.strip().startswith("1. ") or line.strip().startswith("1) "):
                if not in_list or list_type != "ol":
                    if in_list:
                        result_lines.append(f"</{list_type}>")
                    result_lines.append("<ol>")
                    in_list = True
                    list_type = "ol"
                result_lines.append(f"<li>{html.escape(line.strip()[3:])}</li>")
            else:
                if in_list:
                    result_lines.append(f"</{list_type}>")
                    in_list = False
                result_lines.append(line)
        
        if in_list:
            result_lines.append(f"</{list_type}>")
        
        # Handle paragraphs
        markdown_text = "\n".join(result_lines)
        paragraphs = markdown_text.split("\n\n")
        markdown_text = "".join(f"<p>{para}</p>" for para in paragraphs if para.strip())
        
        return markdown_text
    
    def _convert_code_blocks(self, text: str) -> str:
        """
        Convert markdown code blocks to HTML.
        
        Args:
            text: The text containing code blocks
            
        Returns:
            Text with HTML code blocks
        """
        # Handle inline code
        in_backtick = False
        result = []
        i = 0
        
        while i < len(text):
            if text[i:i+3] == "```":
                # Handle code block
                i += 3
                language = ""
                while i < len(text) and text[i] != '\n':
                    language += text[i]
                    i += 1
                
                if i < len(text):
                    i += 1  # Skip newline
                
                code_content = ""
                while i + 2 < len(text) and text[i:i+3] != "```":
                    code_content += text[i]
                    i += 1
                
                if i + 2 < len(text):
                    i += 3  # Skip closing ```
                
                result.append(f"<pre><code class=\"language-{language.strip()}\">{html.escape(code_content)}</code></pre>")
            elif text[i] == '`':
                # Handle inline code
                if in_backtick:
                    result.append("</code>")
                    in_backtick = False
                else:
                    result.append("<code>")
                    in_backtick = True
                i += 1
            else:
                result.append(text[i])
                i += 1
        
        return "".join(result)
    
    def get_extension(self) -> str:
        """
        Get the file extension for HTML output.
        
        Returns:
            File extension "html"
        """
        return "html"
    
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