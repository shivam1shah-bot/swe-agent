"""
AI-Powered Documentation Generator

This module handles the generation of comprehensive API documentation using
autonomous agents with bank-specific context enhancement.
"""

import json
import re
from datetime import datetime
from typing import Dict, Any, Optional, List

from src.providers.logger import Logger
from src.providers.context import Context


class AIDocumentationGenerator:
    """AI-powered API documentation generator with flexible context enhancement"""
    
    def __init__(self, logger: Optional[Logger] = None):
        """Initialize documentation generator with optional logger"""
        self.logger = logger or Logger()
    
    def generate_api_documentation(
        self, 
        parsed_content: str, 
        bank_name: str, 
        custom_prompt: str = "",
        include_examples: bool = True,
        enhance_context: bool = True,
        ctx: Optional[Context] = None
    ) -> str:
        """
        Generate comprehensive API documentation using autonomous agent
        
        Args:
            parsed_content: Extracted document content
            bank_name: Name of the bank for context enhancement
            custom_prompt: Additional custom requirements
            include_examples: Whether to include code examples
            enhance_context: Whether to use bank-specific context
            ctx: Context object for autonomous agent calls
            
        Returns:
            Generated API documentation as string
        """
        self.logger.info(f"Generating API documentation for {bank_name}")
        
        # Create comprehensive prompt
        prompt = self._create_documentation_prompt(
            parsed_content=parsed_content,
            bank_name=bank_name,
            custom_prompt=custom_prompt,
            include_examples=include_examples,
            enhance_context=enhance_context
        )
        
        # Call autonomous agent
        agent_result = self._call_autonomous_agent(prompt, ctx)
        
        if not agent_result.get("success", False):
            error_msg = agent_result.get("error", "Unknown error")
            raise Exception(f"API documentation generation failed: {error_msg}")
        
        # Extract and validate generated documentation
        generated_doc = self._extract_documentation_from_response(agent_result)
        
        if not generated_doc or len(generated_doc.strip()) < 100:
            raise Exception("Generated documentation is too short or empty")
        
        # Post-process and enhance documentation
        enhanced_doc = self._post_process_documentation(generated_doc, bank_name)
        
        self.logger.info(f"Successfully generated API documentation: {len(enhanced_doc)} characters")
        return enhanced_doc
    
    def _create_documentation_prompt(
        self,
        parsed_content: str,
        bank_name: str,
        custom_prompt: str = "",
        include_examples: bool = True,
        enhance_context: bool = True
    ) -> str:
        """Create comprehensive prompt for API documentation generation"""
        
        # Get bank-specific context
        bank_context = ""
        if enhance_context:
            bank_context = self._get_bank_specific_context(bank_name)
        
        # Build examples section
        examples_section = ""
        if include_examples:
            examples_section = self._get_examples_section()
        
        # Create the token-optimized prompt
        prompt = f"""
Act as an API documentation specialist. Parse the provided {bank_name} API integration document to generate a comprehensive technical specification in Markdown. The output must be structured, precise, and ready for integration agent, U.A.T. testing, and code generation.

Extract and format the information into the following sections:

## 1. Security & Authentication

**Authentication**: Detail the method (e.g., OAuth 2.0, API Key, Certificate-based).
**Request Headers**: List all required headers with name, description, and example values.
**Encryption**: Specify the algorithm (e.g., RSA/ECB/PKCS1Padding), the exact payload fields to be encrypted, and the specific key/certificate identifiers to use (e.g., bank_public_cert.pem).
**Decryption**: Specify the algorithm, fields to be decrypted, and the required private key identifier.
**Request Signature**: Detail the signing algorithm (e.g., HMAC-SHA256) and the exact, ordered string-to-sign concatenation format.

## 2. API Endpoints

For each endpoint, provide:
**Endpoint**: [HTTP_METHOD] [URL_PATH] (e.g., POST /api/v1/payments/initiate)
**Description**: A one-sentence summary of its purpose.
**Request Payload**: A markdown table with columns: Field Name, Data Type, Description, Required (Y/N), and Constraints/Example.
**Success Response (200 OK)**: A markdown table with columns: Field Name, Data Type, Description, and Example.
**Code Examples**: Provide complete raw JSON examples for both the request and success response.

## 3. Error Codes & Handling
Create a markdown table listing all possible HTTP Status Codes, Bank Error Codes, Error Messages, and a clear Description/Action Required.
{examples_section}

## Additional Requirements:
{custom_prompt}

## Output Requirements:
- Use exact field names, data types, and security algorithms from the source document
- Include specific key/certificate identifiers and file names
- Provide complete, copy-paste ready JSON examples
- Ensure absolute precision in technical details for implementation
- Format all tables using proper Markdown syntax

Ensure absolute precision in extracting field names, data types, security algorithms, and key identifiers as they are critical for implementation.

## Source Document:
{parsed_content}
"""
        
        return prompt.strip()
    
    def _get_bank_specific_context(self, bank_name: str) -> str:
        """Get generic bank-specific context for enhanced documentation generation"""
        context = f"""
## {bank_name} Integration Context:

This documentation is for {bank_name} API integration. 

**General Focus Areas for {bank_name}:**
- Pay special attention to authentication and security requirements
- Look for encryption specifications and certificate requirements
- Extract timeout and retry policies
- Document any bank-specific error codes or formats
- Identify common banking operations like balance inquiry, fund transfer, and transaction status
- Note any specific data formats or validation rules
- Extract rate limiting and throttling information
- Document sandbox/UAT environment details if mentioned

**Expected API Categories:**
- Account Management (balance inquiry, account details)
- Payment Operations (fund transfer, payment initiation)
- Transaction Management (status inquiry, transaction history)
- Beneficiary Management (add, modify, delete beneficiaries)
- Authentication & Security (login, token management, encryption)

**Common Authentication Patterns in Banking:**
- Certificate-based authentication
- API Key authentication
- OAuth 2.0 flows
- Token-based authentication
- Digital signatures for request validation

Focus on extracting the exact technical specifications from the source document rather than making assumptions.
"""
        
        return context
    
    def _get_examples_section(self) -> str:
        """Get examples section for the prompt"""
        return """
Include practical code examples where possible:
- Sample request/response JSON
- Authentication examples
- Common use case scenarios
- Error response examples
- Integration code snippets (curl, Python, etc.)
"""
    
    def _call_autonomous_agent(self, prompt: str, ctx: Optional[Context]) -> Dict[str, Any]:
        """Call autonomous agent with the documentation generation prompt"""
        try:
            from src.agents.autonomous_agent import AutonomousAgentTool
            
            agent_tool = AutonomousAgentTool()
            result = agent_tool.execute({
                "prompt": prompt,
                "task_id": ctx.get("task_id") if ctx else "api-doc-gen",
                "agent_name": "api-doc-generator",
            })
            
            return result
            
        except Exception as e:
            error_message = f"Autonomous agent execution failed: {str(e)}"
            self.logger.error(error_message)
            return {
                "success": False,
                "error": error_message,
                "result": None
            }
    
    def _extract_documentation_from_response(self, agent_result: Dict[str, Any]) -> str:
        """Extract documentation content from agent response"""
        generated_doc = agent_result.get("result", "")
        
        # Handle case where result might be a dictionary
        if isinstance(generated_doc, dict):
            # Try common keys that might contain the actual content
            generated_doc = (
                generated_doc.get("content", "") or 
                generated_doc.get("text", "") or 
                generated_doc.get("output", "") or 
                generated_doc.get("documentation", "") or
                str(generated_doc)
            )
        
        # Ensure we have a string
        if not isinstance(generated_doc, str):
            generated_doc = str(generated_doc)
        
        return generated_doc.strip()
    
    def _post_process_documentation(self, documentation: str, bank_name: str) -> str:
        """Post-process generated documentation for quality and consistency"""
        
        # Add document header with metadata
        header = f"""# {bank_name} API Documentation

**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**Bank**: {bank_name}
**Type**: Integration API Documentation

---

"""
        
        # Clean up formatting
        documentation = self._clean_documentation_formatting(documentation)
        
        # Add table of contents if not present
        if "## Table of Contents" not in documentation and "# Table of Contents" not in documentation:
            toc = self._generate_table_of_contents(documentation)
            if toc:
                documentation = toc + "\n\n" + documentation
        
        # Ensure proper section spacing
        documentation = re.sub(r'\n(#{1,6}\s)', r'\n\n\1', documentation)
        documentation = re.sub(r'\n\n\n+', '\n\n', documentation)
        
        return header + documentation
    
    def _clean_documentation_formatting(self, text: str) -> str:
        """Clean up documentation formatting"""
        # Fix common formatting issues
        text = re.sub(r'\*\*([^*]+)\*\*:', r'**\1:**', text)  # Fix bold headers
        text = re.sub(r'\n\s*\n\s*\n', '\n\n', text)  # Remove excessive newlines
        text = re.sub(r'^\s+', '', text, flags=re.MULTILINE)  # Remove leading spaces
        
        return text.strip()
    
    def _generate_table_of_contents(self, documentation: str) -> str:
        """Generate table of contents from documentation headers"""
        lines = documentation.split('\n')
        toc_items = []
        
        for line in lines:
            line = line.strip()
            if line.startswith('#'):
                # Count header level
                level = len(line) - len(line.lstrip('#'))
                if level <= 3:  # Only include up to h3
                    title = line.lstrip('#').strip()
                    if title:
                        indent = "  " * (level - 1)
                        # Create anchor link
                        anchor = title.lower().replace(' ', '-').replace('/', '').replace('&', '').replace('(', '').replace(')', '')
                        toc_items.append(f"{indent}- [{title}](#{anchor})")
        
        if toc_items:
            return "## Table of Contents\n\n" + "\n".join(toc_items)
        
        return ""
    
    def format_as_json(self, documentation: str) -> Dict[str, Any]:
        """Convert documentation to structured JSON format"""
        return {
            "title": "API Documentation",
            "generated_at": datetime.now().isoformat(),
            "content": documentation,
            "metadata": {
                "format": "markdown",
                "length": len(documentation),
                "sections": len(re.findall(r'^#+\s', documentation, re.MULTILINE))
            }
        }
    
    def format_as_markdown(self, documentation: str) -> str:
        """Ensure proper markdown formatting"""
        # Documentation should already be in markdown format
        # This method can add any additional markdown-specific formatting
        return documentation 