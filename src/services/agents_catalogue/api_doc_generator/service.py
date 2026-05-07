"""
API Documentation Generator Service

This service handles the complete workflow of generating comprehensive API documentation
from PDF bank specifications using AI-powered document analysis.

Features:
- PDF/document parsing and text extraction
- AI-powered API documentation generation with bank-specific context
- Multi-format output support (txt, json, markdown)
- Quality validation and error recovery
"""

import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, TypedDict, List

from src.providers.context import Context
from src.providers.logger import Logger
from .doc_generator import AIDocumentationGenerator
from .document_parser import DocumentParser
from .validator import APIDocGeneratorValidator
from ..base_service import BaseAgentsCatalogueService



class APIDocGeneratorState(TypedDict):
    """State for API documentation generation workflow"""
    # Input parameters
    document_file_path: str
    bank_name: str
    custom_prompt: str
    include_examples: bool
    enhance_context: bool

    # Processing data
    parsed_content: str
    document_structure: Dict[str, Any]
    generated_documentation: str

    # Output files
    output_file_path: str

    # Status
    workflow_status: str
    error_message: Optional[str]


class APIDocGeneratorService(BaseAgentsCatalogueService):
    """Service for generating comprehensive API documentation from bank specifications"""

    def __init__(self):
        """Initialize the API documentation generator service"""
        super().__init__()

        # Initialize logger
        self.logger = Logger("APIDocGeneratorService")

        # Initialize service name
        self.service_name = "api-doc-generator"

        # Setup directories
        self.setup_directories()

        # Initialize components
        self.document_parser = DocumentParser(self.logger)
        self.doc_generator = AIDocumentationGenerator(self.logger)

    @property
    def description(self) -> str:
        """Service description."""
        return "Generate comprehensive API documentation from bank specification documents using AI-powered analysis"

    def setup_directories(self):
        """Setup required directories for the service"""
        base_dir = Path(__file__).parent.parent.parent.parent.parent / "uploads"

        self.outputs_dir = base_dir / "api_doc_generator" / "outputs"
        self.temp_dir = base_dir / "api_doc_generator" / "temp"

        # Create directories
        self.outputs_dir.mkdir(parents=True, exist_ok=True)
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    def get_service_info(self) -> Dict[str, Any]:
        """Get service information and capabilities"""
        return {
            "service_name": "api-doc-generator",
            "description": "Generate comprehensive API documentation from PDF bank specifications",
            "capabilities": [
                "PDF and document parsing",
                "AI-powered documentation generation",
                "Document structure analysis",
                "Markdown output generation"
            ],
            "input_formats": [".pdf", ".txt", ".doc", ".docx"],
            "output_formats": ["markdown"],
            "supported_banks": ["Any bank - generic approach"]
        }

    def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute API documentation generation workflow
        
        Args:
            parameters: Service parameters including document_file_path, bank_name, etc.
            
        Returns:
            Dictionary containing execution status and results
        """
        try:
            # Validate parameters
            validated_params = self._validate_parameters(parameters)

            # Queue task for asynchronous processing using queue integration
            from src.tasks.queue_integration import queue_integration

            if not queue_integration.is_queue_available():
                return {
                    "status": "failed",
                    "message": "Queue not available",
                    "metadata": {"error": "Queue not available"}
                }

            self.logger.info("Submitting API documentation generation task to queue",
                             extra={
                                 "bank_name": validated_params.get("bank_name")
                             })

            # Submit to queue with api-doc-generator usecase
            task_id = queue_integration.submit_agents_catalogue_task(
                usecase_name="api-doc-generator",
                parameters=validated_params,
                metadata={
                    "service_type": "api_doc_generator",
                    "execution_mode": "async",
                    "priority": "normal",
                    "bank_name": validated_params.get("bank_name")
                }
            )

            if task_id:
                return {
                    "status": "queued",
                    "task_id": task_id,
                    "message": "API documentation generation queued for processing",
                    "estimated_completion": "2-5 minutes"
                }
            else:
                return {
                    "status": "failed",
                    "message": "Failed to queue task"
                }

        except Exception as e:
            self.logger.error(f"Failed to queue API documentation generation task: {str(e)}")
            return {
                "status": "failed",
                "message": str(e)
            }

    def async_execute(self, parameters: Dict[str, Any], ctx: Context) -> Dict[str, Any]:
        """Synchronous execute for worker processing"""
        try:
            task_id = self.get_task_id(ctx)
            log_ctx = self.get_logging_context(ctx)

            self.logger.info("Starting API documentation generation workflow", extra=log_ctx)

            # Validate parameters
            validated_params = self._validate_parameters(parameters)

            # Initialize state
            state = APIDocGeneratorState(
                document_file_path=validated_params["document_file_path"],
                bank_name=validated_params["bank_name"],
                custom_prompt=validated_params.get("custom_prompt", "Generate comprehensive API documentation"),
                include_examples=validated_params.get("include_examples", True),
                enhance_context=validated_params.get("enhance_context", True),
                parsed_content="",
                document_structure={},
                generated_documentation="",
                output_file_path="",
                workflow_status="initialized",
                error_message=None
            )

            # Execute workflow steps synchronously
            # Parse document
            state = self._parse_document(state, ctx)
            if state["workflow_status"] == "error":
                return self._create_error_result(state)

            # Analyze document structure
            state = self._analyze_document_structure(state, ctx)
            if state["workflow_status"] == "error":
                return self._create_error_result(state)

            # Generate documentation
            state = self._generate_documentation(state, ctx)
            if state["workflow_status"] == "error":
                return self._create_error_result(state)

            # Save output files
            state = self._save_output_files(state, ctx)
            if state["workflow_status"] == "error":
                return self._create_error_result(state)

            state["workflow_status"] = "completed"

            # Read output file for UI preview
            file_content = ""
            try:
                if state["output_file_path"] and os.path.exists(state["output_file_path"]):
                    with open(state["output_file_path"], 'r', encoding='utf-8') as f:
                        file_content = f.read()
            except Exception as e:
                self.logger.warning(f"Could not read output file for preview: {str(e)}")

            return {
                "status": "completed",
                "message": "API documentation generation completed successfully",
                "result": {
                    "bank_name": state["bank_name"],
                    "output_file": state["output_file_path"],
                    "file_content": file_content,
                    "document_statistics": state["document_structure"].get("statistics", {}),
                    "generation_metadata": {
                        "processed_at": datetime.now().isoformat(),
                        "include_examples": state["include_examples"],
                        "enhanced_context": state["enhance_context"]
                    }
                }
            }

        except Exception as e:
            self.logger.error(f"API documentation generation failed: {str(e)}")
            return {
                "status": "failed",
                "message": str(e)
            }

    def _validate_parameters(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Validate input parameters using the validator"""
        return APIDocGeneratorValidator.validate_parameters(parameters)

    def _parse_document(self, state: APIDocGeneratorState, ctx: Context) -> APIDocGeneratorState:
        """Parse the input document and extract text content"""
        self.logger.info(f"Parsing document: {state['document_file_path']}")

        try:
            # Parse document using document parser
            parsed_content = self.document_parser.parse_document(state["document_file_path"])

            if not parsed_content or len(parsed_content.strip()) < 100:
                state["error_message"] = f"Document parsing failed or content too short: {state['document_file_path']}"
                state["workflow_status"] = "error"
                return state

            state["parsed_content"] = parsed_content
            state["workflow_status"] = "success"
            self.logger.info(f"Successfully parsed document: {len(parsed_content)} characters extracted")

        except Exception as e:
            self.logger.error(f"Error parsing document: {str(e)}")
            state["error_message"] = str(e)
            state["workflow_status"] = "error"

        return state

    def _analyze_document_structure(self, state: APIDocGeneratorState, ctx: Context) -> APIDocGeneratorState:
        """Analyze document structure to identify key sections and information"""
        self.logger.info("Analyzing document structure")

        try:
            # Extract document structure
            document_structure = self.document_parser.extract_document_structure(state["parsed_content"])

            state["document_structure"] = document_structure
            state["workflow_status"] = "success"

            # Log analysis results
            stats = document_structure.get("statistics", {})
            self.logger.info(f"Document analysis completed: {stats}")

        except Exception as e:
            self.logger.error(f"Error analyzing document structure: {str(e)}")
            state["error_message"] = str(e)
            state["workflow_status"] = "error"

        return state

    def _generate_documentation(self, state: APIDocGeneratorState, ctx: Context) -> APIDocGeneratorState:
        """Generate comprehensive API documentation using AI"""
        self.logger.info(f"Generating API documentation for {state['bank_name']}")

        try:
            # Generate documentation using AI documentation generator
            generated_doc = self.doc_generator.generate_api_documentation(
                parsed_content=state["parsed_content"],
                bank_name=state["bank_name"],
                custom_prompt=state["custom_prompt"],
                include_examples=state["include_examples"],
                enhance_context=state["enhance_context"],
                ctx=ctx
            )

            if not generated_doc or len(generated_doc.strip()) < 200:
                state["error_message"] = "Generated documentation is too short or empty"
                state["workflow_status"] = "error"
                return state

            state["generated_documentation"] = generated_doc
            state["workflow_status"] = "success"
            self.logger.info(f"Successfully generated API documentation: {len(generated_doc)} characters")

        except Exception as e:
            self.logger.error(f"Error generating documentation: {str(e)}")
            state["error_message"] = str(e)
            state["workflow_status"] = "error"

        return state

    def _save_output_files(self, state: APIDocGeneratorState, ctx: Context) -> APIDocGeneratorState:
        """Save generated documentation as markdown file"""
        self.logger.info("Saving markdown documentation")

        try:
            task_id = self.get_task_id(ctx)
            if not task_id:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                task_id = f"task_{timestamp}"

            # Save markdown file
            md_filename = f"api_documentation_{task_id}.md"
            md_path = self.outputs_dir / md_filename

            markdown_content = self.doc_generator.format_as_markdown(state["generated_documentation"])

            with open(md_path, 'w', encoding='utf-8') as f:
                f.write(markdown_content)

            state["output_file_path"] = str(md_path)
            state["workflow_status"] = "success"
            self.logger.info(f"Saved markdown documentation: {md_path}")

        except Exception as e:
            self.logger.error(f"Error saving output file: {str(e)}")
            state["error_message"] = str(e)
            state["workflow_status"] = "error"

        return state

    def _create_error_result(self, state: APIDocGeneratorState) -> Dict[str, Any]:
        """Create error result from state"""
        return {
            "status": "failed",
            "message": state.get("error_message", "Unknown error occurred"),
            "result": {
                "bank_name": state.get("bank_name", ""),
                "workflow_stage": state.get("workflow_status", "unknown"),
                "partial_results": {
                    "parsed_content_length": len(state.get("parsed_content", "")),
                    "document_analyzed": bool(state.get("document_structure")),
                    "documentation_generated": bool(state.get("generated_documentation"))
                }
            }
        }

    def get_downloadable_files(self, task_id: str) -> Dict[str, Dict[str, str]]:
        """
        Get available downloadable files for a task.
        
        Args:
            task_id: Task identifier
            
        Returns:
            Dict mapping file_type to file info dict with 'path' and 'filename'
        """
        downloadable_files = {}
        
        # Common output directories to check
        base_paths = [
            self.outputs_dir,
            Path("/app/uploads/api_doc_generator/outputs"),
            Path("uploads/api_doc_generator/outputs"),
        ]
        
        # File types and their patterns
        file_types = {
            "api_documentation": [f"api_documentation_{task_id}.md", f"api_documentation_{task_id}.txt"],
            "parsed_content": [f"parsed_content_{task_id}.txt"],
            "documentation_structure": [f"documentation_structure_{task_id}.json"]
        }
        
        for file_type, filenames in file_types.items():
            for base_path in base_paths:
                for filename in filenames:
                    file_path = base_path / filename
                    if file_path.exists():
                        downloadable_files[file_type] = {
                            "path": str(file_path),
                            "filename": filename
                        }
                        break
                if file_type in downloadable_files:
                    break
        
        return downloadable_files
    
    def get_supported_file_types(self) -> List[str]:
        """Get list of supported file types for downloads."""
        return [
            "api_documentation",
            "parsed_content",
            "documentation_structure"
        ]

    # Register the service using the global registry instance


from ..registry import service_registry

service_registry.register("api-doc-generator", APIDocGeneratorService)
