import json
from dataclasses import dataclass
import os
import gzip
import base64
import time
from datetime import datetime
from typing import Any, Dict
from src.services.agents_catalogue.base_service import BaseAgentsCatalogueService
from src.providers.config_loader import get_config
from src.services.agents_catalogue.genspec.src.parsers.parser_manager import ParserManager
from src.services.agents_catalogue.genspec.src.formatters.formatter_manager import FormatterManager
from src.services.agents_catalogue.genspec.src.spec_generator import SpecGenerator
from src.services.agents_catalogue.genspec.src.services.architecture_analyzer import ArchitectureAnalyzer
from src.services.agents_catalogue.genspec.src.services.client_factory import build_genspec_config
from src.providers.logger import get_logger
from src.providers.context import Context

@dataclass
class GenSpecConfig:
    """Configuration for GenSpec agent execution."""
    config_path: str = "src/services/agents_catalogue/genspec/config.yaml"

class GenSpecService(BaseAgentsCatalogueService):
    """
    GenSpec Agent Service.

    This service provides functionality to interact with the GenSpec codebase
    and execute its functionalities using the interactive CLI.
    """

    def __init__(self):
        """Initialize the GenSpec service."""
        super().__init__()
        self.logger = get_logger("GenSpecService")
        # Load config and extract genspec config from it
        self.config = build_genspec_config()

        self.parser_manager = ParserManager(self.config)
        self.formatter_manager = FormatterManager()
        
        # Defer SpecGenerator initialization to avoid blocking service registration
        # SpecGenerator initialization includes BedrockClient which makes blocking API calls
        # (list_available_models and _test_model_access), so we lazy-load it on first use
        self._spec_generator = None
        self._spec_generator_error = None
    
    @property
    def spec_generator(self) -> SpecGenerator:
        """
        Get the SpecGenerator instance (lazy-loaded to avoid blocking service registration).
        
        Raises RuntimeError if SpecGenerator initialization fails.
        """
        if self._spec_generator is None:
            if self._spec_generator_error is not None:
                # Previous initialization attempt failed
                raise RuntimeError(f"SpecGenerator is not available - initialization failed: {self._spec_generator_error}")
            
            # First access - try to initialize now
            try:
                self.logger.info("Lazy-loading SpecGenerator (this may take a few seconds for Bedrock connection)")
                self._spec_generator = SpecGenerator(self.config)
                self.logger.info("Successfully initialized SpecGenerator")
            except Exception as e:
                self._spec_generator_error = str(e)
                self.logger.error(f"Failed to initialize SpecGenerator: {str(e)}", exc_info=True)
                raise RuntimeError(f"Failed to initialize SpecGenerator: {str(e)}")
        
        return self._spec_generator
    

    def description(self) -> str:
        """Service description."""
        return "GenSpec Service for generating technical specifications."

    def log_behavior(self, task_id: str, action: str, description: str, status: str = "active") -> None:
        """
        Log agent behavior for a task to create a timeline of actions.
        This writes logs in the format expected by the execution logs UI.
        
        Args:
            task_id: The ID of the task
            action: The action being performed
            description: A description of the action
            status: Status of this log entry ("active" or "completed")
        """
        timestamp = time.time()
        formatted_time = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
        
        behavior_entry = {
            "timestamp": timestamp,
            "formatted_time": formatted_time,
            "action": action,
            "description": description,
            "content": f"[{action}] {description}",  # Required by UI
            "status": status,
            "log_index": int(timestamp * 1000)  # Unique index based on timestamp
        }

        # Create structured directory for logs - using agent-logs as expected by UI
        log_dir = os.path.join("tmp", "logs", "agent-logs")
        os.makedirs(log_dir, exist_ok=True)

        # Save the behavior log to a file - using claude_code_{task_id}.json format
        log_file = os.path.join(log_dir, f"claude_code_{task_id}.json")
        try:
            # Check if file exists
            if os.path.exists(log_file):
                with open(log_file, "r") as f:
                    existing_logs = json.load(f)
                existing_logs.append(behavior_entry)
                logs_to_save = existing_logs
            else:
                logs_to_save = [behavior_entry]
            
            # Write updated logs
            with open(log_file, "w") as f:
                json.dump(logs_to_save, f, indent=2)
            self.logger.debug(f"Saved behavior log for task {task_id}: {action}")
        except Exception as e:
            self.logger.error(f"Error saving behavior log for task {task_id}: {e}")

    def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Synchronous execute for API calls - handles different operation types.
        """
        try:
            # Check if this is a helper operation (not full spec generation)
            operation = parameters.get('operation')
            
            if operation == 'get_auth_url':
                self.logger.info("Processing get_auth_url operation")
                try:
                    auth_url = self.get_auth_url()
                    self.logger.info(f"Successfully generated auth URL (length: {len(auth_url) if auth_url else 0})")
                    # Return in format that will be preserved by format_success_response
                    return {
                        "status": "completed",
                        "message": "OAuth URL generated successfully",
                        "auth_url": auth_url,
                        "metadata": {"auth_url": auth_url}  # Also put in metadata as backup
                    }
                except Exception as e:
                    self.logger.error(f"Error in get_auth_url operation: {str(e)}", exc_info=True)
                    raise
            
            elif operation == 'exchange_code_and_parse':
                code = parameters.get('code')
                prd_document = parameters.get('prdDocument')
                if not code or not prd_document:
                    raise ValueError("code and prdDocument are required")
                parsed_result = self.exchange_code_and_parse_google_doc(code, prd_document)
                # Return in format that will be preserved by format_success_response
                return {
                    "status": "completed",
                    "message": "Google Doc parsed successfully",
                    "parsed_data": parsed_result,
                    "metadata": {"parsed_data": parsed_result}  # Also put in metadata as backup
                }
            
            elif operation == 'analyze_text_architecture':
                text_description = parameters.get('text_description')
                if not text_description:
                    raise ValueError("text_description is required")
                result = self.analyze_text_architecture(text_description)
                return {
                    "data": {
                        "mermaid_diagram": result.get("mermaid_diagram", ""),
                        "components": result.get("components", []),
                        "relationships": result.get("relationships", []),
                        "description": result.get("description", "")
                    }
                }
            
            # Normal operation - generate specification
            # Normalize and validate required parameters
            normalized_parameters = self._normalize_parameters(parameters)
            self._validate_parameters(normalized_parameters)

            # Queue the task using sync queue integration
            from src.tasks.queue_integration import queue_integration

            if not queue_integration.is_queue_available():
                self.logger.error("Queue system is not available - falling back to synchronous execution")
                # Fallback to synchronous execution if queue is not available
                try:
                    # Execute synchronously as a fallback
                    spec_data = self._generate_specification(
                        project_name=normalized_parameters.get('project_name'),
                        problem_statement=normalized_parameters.get('problem_statement'),
                        parsed_data=normalized_parameters.get('parsed_data', {})
                    )
                    
                    # Format and save the specification
                    markdown_content = self.formatter_manager.format_spec(spec_data, "markdown")
                    markdown_path = f"./output/{normalized_parameters.get('project_name', 'spec').replace(' ', '_')}_spec.md"
                    os.makedirs(os.path.dirname(markdown_path), exist_ok=True)
                    
                    with open(markdown_path, 'w', encoding='utf-8') as f:
                        f.write(markdown_content)
                    
                    self.logger.info(f"Specification generated synchronously: {markdown_path}")
                                        
                    return {
                        "status": "success",
                        "message": "Specification generated successfully (synchronous fallback)",
                        "task_id": None,
                        "files": [{"name": os.path.basename(markdown_path), "path": markdown_path}],
                        "markdown_path": markdown_path,
                        "metadata": {
                            "execution_mode": "synchronous_fallback",
                            "project_name": normalized_parameters.get('project_name'),
                            "files_generated": [markdown_path]
                        }
                    }
                except Exception as sync_error:
                    self.logger.error(f"Synchronous fallback also failed: {sync_error}")
                    return {
                        "status": "failed",
                        "message": f"Both async and sync execution failed: {str(sync_error)}",
                        "metadata": {"error": str(sync_error), "queue_available": False}
                    }

            self.logger.info("Submitting GenSpec task to queue",
                           extra={
                               "project_name": normalized_parameters.get("project_name"),
                               "has_architecture": bool(normalized_parameters.get("parsed_data", {}).get("architecture")),
                               "has_api_docs": bool(normalized_parameters.get("parsed_data", {}).get("api_documentation"))
                           })

            # Compress parameters to avoid database size limits
            compressed_parameters = self._compress_parameters(normalized_parameters)
            
            # Submit to queue with genspec-specific task type
            task_id = queue_integration.submit_agents_catalogue_task(
                usecase_name="genspec-agent",
                parameters={"compressed_data": compressed_parameters},  # Store compressed data
                metadata={
                    "service_type": "genspec",
                    "execution_mode": "async",
                    "priority": "normal",
                    "project_name": normalized_parameters.get("project_name"),
                    "has_architecture": bool(normalized_parameters.get("parsed_data", {}).get("architecture")),
                    "has_api_docs": bool(normalized_parameters.get("parsed_data", {}).get("api_documentation")),
                    "compressed": True  # Mark as compressed
                }
            )
            
            if task_id:
                self.logger.info(f"GenSpec task {task_id} submitted to queue successfully")
                return {
                    "status": "success",
                    "message": "GenSpec task queued for processing",
                    "task_id": task_id,
                    "metadata": {
                        "task_id": task_id,
                        "project_name": normalized_parameters.get("project_name"),
                        "execution_mode": "async"
                    }
                }
            else:
                self.logger.error("Queue submission failed - falling back to synchronous execution")
                # Fallback to synchronous execution if queue submission fails
                try:
                    # Execute synchronously as a fallback
                    spec_data = self._generate_specification(
                        project_name=normalized_parameters.get('project_name'),
                        problem_statement=normalized_parameters.get('problem_statement'),
                        parsed_data=normalized_parameters.get('parsed_data', {})
                    )
                    
                    # Format and save the specification
                    markdown_content = self.formatter_manager.format_spec(spec_data, "markdown")
                    markdown_path = f"./output/{normalized_parameters.get('project_name', 'spec').replace(' ', '_')}_spec.md"
                    os.makedirs(os.path.dirname(markdown_path), exist_ok=True)
                    
                    with open(markdown_path, 'w', encoding='utf-8') as f:
                        f.write(markdown_content)
                    
                    self.logger.info(f"Specification generated synchronously (queue fallback): {markdown_path}")
                    
                    return {
                        "status": "success",
                        "message": "Specification generated successfully (synchronous fallback due to queue failure)",
                        "task_id": None,
                        "files": [{"name": os.path.basename(markdown_path), "path": markdown_path}],
                        "markdown_path": markdown_path,
                        "metadata": {
                            "execution_mode": "synchronous_fallback",
                            "project_name": normalized_parameters.get('project_name'),
                            "files_generated": [markdown_path],
                            "queue_failure": True
                        }
                    }
                except Exception as sync_error:
                    self.logger.error(f"Synchronous fallback also failed: {sync_error}")
                    return {
                        "status": "failed",
                        "message": f"Both async and sync execution failed: {str(sync_error)}",
                        "metadata": {"error": str(sync_error), "queue_submission_failed": True}
                    }
                
        except Exception as e:
            self.logger.error(f"Failed to execute GenSpec: {e}")
            return {
                "status": "failed",
                "message": f"Failed to execute GenSpec: {str(e)}",
                "metadata": {"error": str(e)}
            }

    def async_execute(self, parameters: Dict[str, Any], ctx: Context) -> Dict[str, Any]:
        """
        Asynchronous execute for worker processing - performs the actual specification generation.
        
        Args:
            parameters: Dictionary containing:
                - project_name: Name of the project
                - problem_statement: Problem statement text
                - parsed_data: Dictionary of parsed input data
            ctx: Execution context with task_id, metadata, cancellation, and logging correlation
            
        Returns:
            Dictionary containing:
                - status: "completed" or "failed"
                - message: Status message
                - files: List of generated files
                - markdown_path: Path to generated markdown file
        """
        try:
            # Extract task information from context
            task_id = self.get_task_id(ctx)
            metadata = self.get_metadata(ctx)
            execution_mode = self.get_execution_mode(ctx)
            log_ctx = self.get_logging_context(ctx)

            self.logger.info("Starting async GenSpec specification generation",
                           extra={
                               **log_ctx,
                               "parameters": {k: v for k, v in parameters.items() if not k.startswith('_')},
                               "execution_mode": execution_mode
                           })
            
            # Log start of execution
            self.log_behavior(task_id, "start_execution", "Starting GenSpec specification generation", "active")

            # Check if context is already done before starting
            if self.check_context_done(ctx):
                context_status = self.get_context_status(ctx)
                error_msg = "Context is done before specification generation"
                if ctx.is_cancelled():
                    error_msg = "Context was cancelled before specification generation"
                elif ctx.is_expired():
                    error_msg = "Context expired before specification generation"

                self.logger.warning(error_msg, extra=log_ctx)
                return {
                    "status": "failed",
                    "message": error_msg,
                    "files": [],
                    "markdown_path": None,
                    "agent_result": {"success": False, "error": error_msg},
                    "metadata": {
                        "error": error_msg,
                        "task_id": task_id,
                        "context_status": context_status
                    }
                }

            # Handle compressed parameters if present
            if 'compressed_data' in parameters:
                # Decompress the parameters
                self.log_behavior(task_id, "decompress_parameters", "Decompressing task parameters", "active")
                compressed_data = parameters['compressed_data']
                decompressed_parameters = self._decompress_parameters(compressed_data)
                self.logger.info("Successfully decompressed parameters for async execution")
            else:
                # Use parameters directly (backward compatibility)
                decompressed_parameters = parameters
                self.logger.info("Using uncompressed parameters for async execution")

            # Validate parameters
            self.log_behavior(task_id, "validate_parameters", "Validating input parameters", "active")
            self._validate_parameters(decompressed_parameters)

            # Extract parameters
            project_name = decompressed_parameters.get('project_name')
            problem_statement = decompressed_parameters.get('problem_statement')
            parsed_data = decompressed_parameters.get('parsed_data', {})

            if not project_name:
                raise ValueError("project_name is required")
            if not problem_statement:
                raise ValueError("problem_statement is required")

            self.logger.info(f"Generating specification for project: {project_name}", extra=log_ctx)
            self.log_behavior(task_id, "start_generation", f"Generating specification for: {project_name}", "active")

            # Generate the specification
            spec_data = self._generate_specification(
                project_name=project_name,
                problem_statement=problem_statement,
                parsed_data=parsed_data
            )
            
            sections_count = len(spec_data.get('sections', []))
            self.log_behavior(task_id, "spec_generated", f"Generated {sections_count} specification sections", "active")

            # Format and save the specification
            self.log_behavior(task_id, "format_spec", "Formatting specification as Markdown", "active")
            markdown_content = self.formatter_manager.format_spec(spec_data, "markdown")
            markdown_path = f"./output/{project_name.replace(' ', '_')}_spec.md"
            os.makedirs(os.path.dirname(markdown_path), exist_ok=True)
            
            with open(markdown_path, 'w', encoding='utf-8') as f:
                f.write(markdown_content)

            self.logger.info(f"Specification generated successfully: {markdown_path}", extra=log_ctx)
            self.log_behavior(task_id, "save_spec", f"Saved specification to: {markdown_path}", "completed")

            return {
                "status": "completed",
                "message": "Specification generated successfully",
                "files": [{"name": os.path.basename(markdown_path), "path": markdown_path}],
                "markdown_path": markdown_path,
                "agent_result": {
                    "success": True,
                    "spec_data": spec_data,
                    "markdown_path": markdown_path
                },
                "metadata": {
                    "task_id": task_id,
                    "project_name": project_name,
                    "files_generated": [markdown_path],
                    "spec_sections": len(spec_data.get('sections', []))
                }
            }

        except Exception as e:
            # Get task_id for error logging (might not be set if error is early)
            try:
                task_id = self.get_task_id(ctx) if 'ctx' in locals() else parameters.get('task_id', 'unknown')
            except:
                task_id = 'unknown'
            
            # Log full traceback for debugging
            import traceback
            error_traceback = traceback.format_exc()
            
            # Build log context
            error_log_ctx = log_ctx if 'log_ctx' in locals() else {}
            error_log_ctx.update({
                "error": str(e),
                "error_type": type(e).__name__,
                "traceback": error_traceback
            })
            
            self.logger.error(f"Failed to execute GenSpec async: {e}", extra=error_log_ctx)
            
            # Log error to execution logs
            if task_id and task_id != 'unknown':
                self.log_behavior(task_id, "error", f"Generation failed: {str(e)}", "completed")
            
            return {
                "status": "failed",
                "message": f"Failed to generate specification: {str(e)}",
                "files": [],
                "markdown_path": None,
                "agent_result": {
                    "success": False,
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "traceback": error_traceback[:500]  # First 500 chars of traceback
                },
                "metadata": {
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "task_id": task_id,
                    "project_name": parameters.get('project_name', 'unknown')
                }
            }

    def _generate_specification(self, project_name: str, problem_statement: str, parsed_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate the technical specification using SpecGenerator.
        """
        try:
            # This will trigger lazy initialization of SpecGenerator if not already done
            self.logger.info("Accessing SpecGenerator (may trigger initialization)")
            spec_data = self.spec_generator.generate_spec(
                project_name=project_name,
                problem_statement=problem_statement,
                parsed_data=parsed_data
            )
            return spec_data
        except RuntimeError as e:
            # SpecGenerator initialization failed
            self.logger.error(f"SpecGenerator initialization failed: {e}")
            raise RuntimeError(f"Failed to initialize AI model connection: {str(e)}. Please check Vertex AI/Bedrock configuration.")
        except Exception as e:
            self.logger.error(f"Failed to generate specification: {e}")
            raise 
    def analyze_text_architecture(self, text_description: str) -> Dict[str, Any]:
        """
        Analyze the text description using the ArchitectureAnalyzer.
        """
        try:
            analyzer = ArchitectureAnalyzer(self.config)
            flowchart_result = analyzer.analyze_text_architecture(text_description)
            return flowchart_result
        except Exception as e:
            self.logger.error(f"Failed to analyze text architecture: {e}")
            raise
    def get_auth_url(self) -> str:
        """
        Get Google OAuth authorization URL for Google Drive access.
        
        Returns:
            OAuth URL string
        """
        from src.providers.auth.google_oauth_provider import GoogleDriveOAuthProvider
        oauth_provider = GoogleDriveOAuthProvider(self.config)
        return oauth_provider.get_auth_url()

    def exchange_code_and_parse_google_doc(self, code: str, prd_document: str) -> Dict[str, Any]:
        """
        Exchange OAuth code for token and parse Google Doc content.
        
        Args:
            code: OAuth authorization code
            prd_document: Google Doc URL
            
        Returns:
            Parsed content dictionary
        """
        from src.providers.auth.google_oauth_provider import GoogleDriveOAuthProvider
        from src.services.file.parsing_service import FileParsingService
        
        # Initialize providers
        oauth_provider = GoogleDriveOAuthProvider(self.config)
        parsing_service = FileParsingService()
        
        # Exchange code for token
        oauth_provider.exchange_code_for_token(code)
        
        # Parse Google Doc
        result = parsing_service.parse_google_doc(prd_document, oauth_provider)
        
        return result

    def _normalize_parameters(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize and clean parameters for GenSpec execution.
        
        Args:
            parameters: Raw parameters from API request
            
        Returns:
            Normalized parameters dictionary
        """
        normalized = {}
        
        # Handle different input formats
        if 'data' in parameters:
            # Handle the old format where data is a JSON string
            try:
                if isinstance(parameters['data'], str):
                    data = json.loads(parameters['data'])
                else:
                    data = parameters['data']
                
                # Extract from parsed_data structure
                parsed_data = data.get('parsed_data', {})
                normalized['project_name'] = parsed_data.get('title', '')
                normalized['problem_statement'] = parsed_data.get('problem_statement', '')
                normalized['parsed_data'] = parsed_data
            except (json.JSONDecodeError, KeyError) as e:
                self.logger.warning(f"Failed to parse data parameter: {e}")
                raise ValueError(f"Invalid data parameter format: {e}")
        else:
            # Handle direct parameter format - the UI sends parameters directly
            # Extract project_name and problem_statement from the parameters
            normalized['project_name'] = parameters.get('title', '')
            normalized['problem_statement'] = parameters.get('problem_statement', '')
            
            # The entire parameters object becomes the parsed_data
            normalized['parsed_data'] = parameters
        
        # Consolidate architecture image to single location BEFORE compression
        normalized = self._consolidate_architecture_image(normalized)
        
        return normalized

    def _consolidate_architecture_image(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Consolidate architecture image to single location to avoid duplication.
        
        Args:
            parameters: Parameters dictionary
            
        Returns:
            Parameters dictionary with consolidated architecture image
        """
        try:
            parsed_data = parameters.get('parsed_data', {})
            if not isinstance(parsed_data, dict):
                return parameters
            
            # Find architecture image from various locations
            architecture_image = None
            
            # Check current_architecture field (top level)
            if 'current_architecture' in parsed_data and isinstance(parsed_data['current_architecture'], str):
                if parsed_data['current_architecture'].startswith('data:image/'):
                    architecture_image = parsed_data['current_architecture']
            
            # Check prd.sections.current_architecture
            if not architecture_image and 'prd' in parsed_data:
                prd_data = parsed_data.get('prd', {})
                if isinstance(prd_data, dict) and 'sections' in prd_data:
                    sections = prd_data.get('sections', {})
                    if isinstance(sections, dict) and 'current_architecture' in sections:
                        if isinstance(sections['current_architecture'], str) and sections['current_architecture'].startswith('data:image/'):
                            architecture_image = sections['current_architecture']
            
            # Check architecture.content
            if not architecture_image and 'architecture' in parsed_data:
                arch_data = parsed_data.get('architecture', {})
                if isinstance(arch_data, dict) and 'content' in arch_data:
                    if isinstance(arch_data['content'], str) and arch_data['content'].startswith('data:image/'):
                        architecture_image = arch_data['content']
            
            # If we found an architecture image, consolidate it to architecture.content only
            if architecture_image:
                # Ensure architecture object exists
                if 'architecture' not in parsed_data:
                    parsed_data['architecture'] = {}
                
                # Set the architecture image only in architecture.content
                parsed_data['architecture']['content'] = architecture_image
                parsed_data['architecture']['type'] = 'image'
                parsed_data['architecture']['file_name'] = 'architecture_diagram.png'
                
                # Remove duplicates
                if 'current_architecture' in parsed_data:
                    del parsed_data['current_architecture']
                
                if 'prd' in parsed_data and isinstance(parsed_data['prd'], dict):
                    prd_data = parsed_data['prd']
                    if 'sections' in prd_data and isinstance(prd_data['sections'], dict):
                        if 'current_architecture' in prd_data['sections']:
                            del prd_data['sections']['current_architecture']
                    
                    # Also remove from prd.architecture.content if it exists
                    if 'architecture' in prd_data and isinstance(prd_data['architecture'], dict):
                        if 'content' in prd_data['architecture'] and isinstance(prd_data['architecture']['content'], str):
                            if prd_data['architecture']['content'].startswith('data:image/'):
                                del prd_data['architecture']['content']
            
            return parameters
            
        except Exception as e:
            self.logger.warning(f"Failed to consolidate architecture image: {e}")
            return parameters

    def _validate_parameters(self, parameters: Dict[str, Any]) -> None:
        """
        Validate required parameters for GenSpec execution.
        
        Args:
            parameters: Normalized parameters dictionary
            
        Raises:
            ValueError: If required parameters are missing or invalid
        """
        if not parameters.get('project_name'):
            raise ValueError("project_name is required")
        
        if not parameters.get('problem_statement'):
            raise ValueError("problem_statement is required")
        
        parsed_data = parameters.get('parsed_data', {})
        if not isinstance(parsed_data, dict):
            raise ValueError("parsed_data must be a dictionary")

    def _compress_parameters(self, parameters: Dict[str, Any]) -> str:
        """
        Compress parameters to reduce database storage size.
        
        Args:
            parameters: Parameters dictionary to compress
            
        Returns:
            Base64-encoded compressed JSON string
        """
        try:
            # Create a copy to avoid modifying original
            params_copy = parameters.copy()
            
            # Remove large image data to reduce size
            if 'parsed_data' in params_copy:
                parsed_data = params_copy['parsed_data'].copy()
                
                # Remove large base64 image data from architecture (consolidated location)
                if 'architecture' in parsed_data and isinstance(parsed_data['architecture'], dict):
                    arch_copy = parsed_data['architecture'].copy()
                    if 'content' in arch_copy and isinstance(arch_copy['content'], str) and len(arch_copy['content']) > 1000:
                        # Replace large base64 data with placeholder
                        arch_copy['content'] = f"[LARGE_IMAGE_DATA_REMOVED:{len(arch_copy['content'])}_chars]"
                        parsed_data['architecture'] = arch_copy
                
                # Remove any remaining large base64 image data from other locations
                if 'current_architecture' in parsed_data and isinstance(parsed_data['current_architecture'], str):
                    if len(parsed_data['current_architecture']) > 1000:
                        parsed_data['current_architecture'] = f"[LARGE_IMAGE_DATA_REMOVED:{len(parsed_data['current_architecture'])}_chars]"
                
                # Remove large content from PRD to reduce database size
                if 'prd' in parsed_data and isinstance(parsed_data['prd'], dict):
                    prd_data = parsed_data['prd'].copy()
                    
                    # Remove large content field (662 kB of text content)
                    if 'content' in prd_data and isinstance(prd_data['content'], str) and len(prd_data['content']) > 10000:
                        prd_data['content'] = f"[LARGE_CONTENT_REMOVED:{len(prd_data['content'])}_chars]"
                    
                    if 'sections' in prd_data and isinstance(prd_data['sections'], dict):
                        sections_copy = prd_data['sections'].copy()
                        for section_key, section_value in sections_copy.items():
                            if isinstance(section_value, str) and section_value.startswith('data:image/') and len(section_value) > 1000:
                                sections_copy[section_key] = f"[LARGE_IMAGE_DATA_REMOVED:{len(section_value)}_chars]"
                            elif isinstance(section_value, str) and len(section_value) > 5000:
                                # Also remove very large text sections
                                sections_copy[section_key] = f"[LARGE_SECTION_REMOVED:{len(section_value)}_chars]"
                        prd_data['sections'] = sections_copy
                    
                    # Also remove from prd.architecture.content
                    if 'architecture' in prd_data and isinstance(prd_data['architecture'], dict):
                        arch_copy = prd_data['architecture'].copy()
                        if 'content' in arch_copy and isinstance(arch_copy['content'], str) and len(arch_copy['content']) > 1000:
                            arch_copy['content'] = f"[LARGE_IMAGE_DATA_REMOVED:{len(arch_copy['content'])}_chars]"
                            prd_data['architecture'] = arch_copy
                    
                    parsed_data['prd'] = prd_data
                
                params_copy['parsed_data'] = parsed_data
            
            # Convert to JSON string
            json_str = json.dumps(params_copy, separators=(',', ':'))
            
            # Compress using gzip
            compressed_data = gzip.compress(json_str.encode('utf-8'))
            
            # Encode to base64 for safe storage
            compressed_b64 = base64.b64encode(compressed_data).decode('utf-8')
            
            # Add marker to indicate this is compressed data
            return f"COMPRESSED:{compressed_b64}"
            
        except Exception as e:
            self.logger.warning(f"Failed to compress parameters, using uncompressed: {e}")
            # Fallback to regular JSON if compression fails
            return json.dumps(parameters, separators=(',', ':'))

    def _decompress_parameters(self, compressed_data: str) -> Dict[str, Any]:
        """
        Decompress parameters from database storage.
        
        Args:
            compressed_data: Compressed parameters string from database
            
        Returns:
            Decompressed parameters dictionary
        """
        try:
            # Check if data is compressed
            if compressed_data.startswith("COMPRESSED:"):
                # Extract base64 data
                b64_data = compressed_data[11:]  # Remove "COMPRESSED:" prefix
                
                # Decode from base64
                compressed_bytes = base64.b64decode(b64_data.encode('utf-8'))
                
                # Decompress using gzip
                json_str = gzip.decompress(compressed_bytes).decode('utf-8')
                
                # Parse JSON
                return json.loads(json_str)
            else:
                # Regular JSON data (backward compatibility)
                return json.loads(compressed_data)
                
        except Exception as e:
            self.logger.error(f"Failed to decompress parameters: {e}")
            # Try to parse as regular JSON as fallback
            try:
                return json.loads(compressed_data)
            except:
                return {}

# Register the service using the global registry instance
from .registry import service_registry
service_registry.register("genspec-agent", GenSpecService)
