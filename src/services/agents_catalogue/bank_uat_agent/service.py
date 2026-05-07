"""
Bank UAT Agent Service

This service handles comprehensive UAT testing of bank API integrations with
advanced encryption support including RSA and AES.

Features:
- API documentation analysis and URL extraction
- RSA encryption with public/private key support  
- AES encryption (legacy compatibility)
- Comprehensive curl generation and execution
- Advanced response analysis and decryption
"""

import os
import re
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, TypedDict, List

from src.providers.context import Context
from src.providers.logger import Logger
from .aes_crypto_manager import AESCryptoManager
from .ai import CryptoAnalyzer, AIConfigValidator, TemplateRecommendationEngine
from .config import EncryptionConfig, AIExtractedConfig
from .crypto import ConfigurableCryptoManager
from .curl_generator import CurlCommandGenerator
from .error_handler import EnhancedErrorHandler
from .file_manager import FileManager
from .rsa_crypto_manager import RSACryptoManager
from .uat_executor import UATExecutor
from .validator import BankUATValidator
from ..base_service import BaseAgentsCatalogueService


class BankUATState(TypedDict):
    """State for Bank UAT testing workflow"""
    # Input parameters
    api_doc_path: str
    bank_name: str
    encryption_type: str
    generate_encrypted_curls: bool
    bank_public_cert_path: Optional[str]  # Bank's public certificate (for encrypting requests TO bank)
    private_key_path: Optional[str]  # Partner's private key (for decrypting responses FROM bank)
    partner_public_key_path: Optional[str]  # Partner's public key (for bank to encrypt responses TO partner)
    encryption_template: Optional[str]
    timeout_seconds: int
    include_response_analysis: bool
    custom_headers: Dict[str, str]
    custom_prompt: Optional[str]

    # AI-enhanced parameters
    enable_ai_analysis: bool
    ai_confidence_threshold: float
    manual_config_override: Optional[Dict[str, Any]]

    # Processing data
    api_doc_content: str
    bank_public_cert_pem: Optional[str]  # Bank certificate content
    private_key_pem: Optional[str]  # Partner private key content
    partner_public_key_pem: Optional[str]  # Partner public key content
    aes_key: Optional[str]  # AES key in hex format
    extracted_urls: Dict[str, str]
    generated_curls: List[str]

    # AI analysis results
    ai_extracted_config: Optional[AIExtractedConfig]
    final_encryption_config: Optional[EncryptionConfig]
    ai_validation_report: Optional[Dict[str, Any]]
    template_recommendations: Optional[Dict[str, Any]]

    # Key handling metadata
    keys_are_real: bool
    key_source: str
    public_key_reference: Optional[str]
    private_key_reference: Optional[str]

    # Results
    uat_results: Dict[str, Any]
    output_files: Dict[str, str]

    # Status
    workflow_status: str
    error_message: Optional[str]


class BankUATService(BaseAgentsCatalogueService):
    """Service for comprehensive bank UAT testing with multi-crypto support"""

    def __init__(self):
        """Initialize the bank UAT service"""
        super().__init__()

        # Initialize logger
        self.logger = Logger("BankUATService")

        # Initialize service name
        self.service_name = "bank-uat-agent"

        # Setup directories
        self.setup_directories()

        # Initialize components
        self.curl_generator = CurlCommandGenerator(self.logger)
        self.uat_executor = UATExecutor(self.logger)
        self.rsa_crypto = RSACryptoManager(self.logger)
        self.aes_crypto = AESCryptoManager(self.logger)

        # Initialize AI-powered components
        self.crypto_analyzer = CryptoAnalyzer(self.logger)
        self.ai_validator = AIConfigValidator(self.logger)
        self.template_recommender = TemplateRecommendationEngine(self.logger)
        self.configurable_crypto = ConfigurableCryptoManager(self.logger)

        self.file_manager = FileManager(
            outputs_dir=self.outputs_dir,
            temp_dir=self.temp_dir,
            archive_dir=self.outputs_dir / "archive",
            logger=self.logger
        )
        self.error_handler = EnhancedErrorHandler(self.logger)

    @property
    def description(self) -> str:
        """Service description."""
        return "Execute comprehensive UAT tests for bank API integrations with conditional encryption support (RSA, AES, Hybrid) based on user preference"

    def setup_directories(self):
        """Setup required directories for the service"""
        base_dir = Path(__file__).parent.parent.parent.parent.parent / "uploads"

        self.outputs_dir = base_dir / "bank_uat_agent" / "outputs"
        self.temp_dir = base_dir / "bank_uat_agent" / "temp"

        # Create directories
        self.outputs_dir.mkdir(parents=True, exist_ok=True)
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    def get_service_info(self) -> Dict[str, Any]:
        """Get service information and capabilities"""
        return {
            "service_name": "bank-uat-agent",
            "description": "Comprehensive UAT testing for bank API integrations with advanced encryption",
            "capabilities": [
                "API documentation analysis",
                "UAT host configuration for endpoint testing",
                "Conditional curl encryption based on user preference",
                "RSA encryption with public/private keys",
                "AES encryption (legacy compatibility)",
                "Hybrid encryption (RSA + AES)",
                "Multi-scenario testing (success, error, boundary, security)",
                "Advanced response analysis and decryption",
                "Performance metrics and validation"
            ],
            "required_parameters": [
                "api_doc_path - Path to API documentation file",
                "bank_name - Name of the bank/institution",
                "uat_host - UAT environment host URL (no validation applied)"
            ],
            "optional_parameters": [
                "encryption_type - Type of encryption (auto_detect, hybrid, none)",
                "generate_encrypted_curls - Boolean to control curl encryption (default: false)",
                "bank_public_cert_path - Path to bank's public certificate for encrypting requests TO the bank (.pem, .crt, .cer)",
                "private_key_path - Path to partner's private key for decrypting responses FROM the bank (.pem, .key)",
                "partner_public_key_path - Path to partner's public key for bank to encrypt responses TO partner (.pem)",
                "aes_key - AES key in hexadecimal format (32/48/64 chars)",
                "apis_to_test - Specific APIs to test",
                "custom_headers - Additional HTTP headers",
                "custom_prompt - Custom testing instructions",
                "enable_ai_analysis - Enable AI-powered configuration analysis",
                "ai_confidence_threshold - Minimum confidence for AI recommendations"
            ],
            "encryption_types": ["auto_detect", "hybrid", "none"],

            "supported_banks": [
                "Any Bank"
            ],
            "input_formats": [".txt", ".json", ".md", ".pdf"],
            "key_formats": {
                "certificates": [".pem", ".crt", ".cer"],
                "private_keys": [".pem", ".key"],
                "supported_standards": ["PKCS#1", "PKCS#8", "X.509"]
            }
        }

    def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute bank UAT testing workflow
        
        Args:
            parameters: Service parameters including api_doc_path, bank_name, encryption settings, etc.
            
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

            self.logger.info("Submitting bank UAT testing task to queue",
                             extra={
                                 "bank_name": validated_params.get("bank_name"),
                                 "uat_host": validated_params.get("uat_host"),
                                 "generate_encrypted_curls": validated_params.get("generate_encrypted_curls"),
                                 "apis_to_test": validated_params.get("apis_to_test"),
                                 "encryption_type": validated_params.get("encryption_type")
                             })

            # Submit to queue with bank-uat-agent usecase
            task_id = queue_integration.submit_agents_catalogue_task(
                usecase_name="bank-uat-agent",
                parameters=validated_params,
                metadata={
                    "service_type": "bank_uat_agent",
                    "execution_mode": "async",
                    "priority": "normal",
                    "bank_name": validated_params.get("bank_name"),
                    "uat_host": validated_params.get("uat_host"),
                    "generate_encrypted_curls": validated_params.get("generate_encrypted_curls"),
                    "encryption_type": validated_params.get("encryption_type")
                }
            )

            if task_id:
                return {
                    "status": "queued",
                    "task_id": task_id,
                    "message": "Bank UAT testing queued for processing",
                    "estimated_completion": "3-8 minutes"
                }
            else:
                return {
                    "status": "failed",
                    "message": "Failed to queue task"
                }

        except Exception as e:
            self.logger.error(f"Failed to queue bank UAT testing task: {str(e)}")
            return {
                "status": "failed",
                "message": str(e)
            }

    def async_execute(self, parameters: Dict[str, Any], ctx: Context) -> Dict[str, Any]:
        """Synchronous execute for worker processing"""
        try:
            task_id = self.get_task_id(ctx)
            log_ctx = self.get_logging_context(ctx)

            self.logger.info("Starting bank UAT testing workflow", extra=log_ctx)

            # Validate parameters
            validated_params = self._validate_parameters(parameters)

            state = BankUATState(
                api_doc_path=validated_params["api_doc_path"],
                bank_name=validated_params["bank_name"],
                encryption_type=validated_params.get("encryption_type", "auto_detect"),
                generate_encrypted_curls=validated_params.get("generate_encrypted_curls", False),
                bank_public_cert_path=validated_params.get("bank_public_cert_path"),
                private_key_path=validated_params.get("private_key_path"),
                partner_public_key_path=validated_params.get("partner_public_key_path"),
                encryption_template=validated_params.get("encryption_template"),
                timeout_seconds=validated_params.get("timeout_seconds", 120),
                include_response_analysis=validated_params.get("include_response_analysis", True),
                custom_headers=validated_params.get("custom_headers", {}),
                custom_prompt=validated_params.get("custom_prompt"),

                # AI-enhanced parameters
                enable_ai_analysis=validated_params.get("enable_ai_analysis", True),
                ai_confidence_threshold=validated_params.get("ai_confidence_threshold", 0.6),
                manual_config_override=validated_params.get("manual_config_override"),

                # Processing data
                api_doc_content="",
                bank_public_cert_pem=None,
                private_key_pem=None,
                partner_public_key_pem=None,
                aes_key=validated_params.get("aes_key"),
                extracted_urls={},
                generated_curls=[],

                # AI analysis results
                ai_extracted_config=None,
                final_encryption_config=None,
                ai_validation_report=None,
                template_recommendations=None,

                # Key handling metadata
                keys_are_real=False,
                key_source="none",
                public_key_reference=None,
                private_key_reference=None,
                uat_results={},
                output_files={},
                workflow_status="initialized",
                error_message=None
            )

            # Execute workflow steps
            state = self._load_api_documentation(state, ctx)
            if state["workflow_status"] == "error":
                return self._create_error_result(state)

            # Determine execution path based on template, keys, and encryption flag
            execution_path = self._determine_execution_path(state)
            self.logger.info(f"Determined execution path: {execution_path}")

            if execution_path == "full_execution":
                # Template + keys + encryption flag present - continue with full execution
                self.logger.info("Full execution path - template and keys available")
                state = self._apply_template_configuration(state, ctx)
                if state["workflow_status"] == "error":
                    return self._create_error_result(state)

            elif execution_path == "config_generation":
                # Missing template/keys - generate config and stop for user download
                self.logger.info("Config generation path - generating encryption configuration for download")
                state = self._generate_encryption_config_for_download(state, ctx)
                return self._create_config_generation_result(state, ctx)

            elif execution_path == "no_encryption":
                # No encryption needed - continue with normal execution
                self.logger.info("No encryption path - continuing with normal UAT execution")
                state["workflow_status"] = "encryption_skipped"

            state = self._extract_uat_host(state, ctx)
            if state["workflow_status"] == "error":
                return self._create_error_result(state)

            state = self._extract_api_urls(state, ctx)
            if state["workflow_status"] == "error":
                return self._create_error_result(state)

            state = self._generate_curl_commands(state, ctx)
            if state["workflow_status"] == "error":
                return self._create_error_result(state)

            state = self._load_encryption_keys(state, ctx)
            if state["workflow_status"] == "error":
                return self._create_error_result(state)

            state = self._execute_uat_tests(state, ctx)
            if state["workflow_status"] == "error":
                return self._create_error_result(state)

            state = self._save_results(state, ctx)
            if state["workflow_status"] == "error":
                return self._create_error_result(state)

            state["workflow_status"] = "completed"

            # Cleanup temporary files
            try:
                self.rsa_crypto.cleanup_temporary_files if hasattr(self.rsa_crypto, 'cleanup_temporary_files') else None
                self.aes_crypto.cleanup_temporary_files()
                self.file_manager.manual_cleanup_if_needed()
            except Exception as e:
                self.logger.warning(f"Could not complete cleanup: {str(e)}")

            # Read output file contents for UI preview
            file_contents = {}
            try:
                for file_type, file_path in state["output_files"].items():
                    if os.path.exists(file_path):
                        with open(file_path, 'r', encoding='utf-8') as f:
                            file_contents[file_type] = f.read()
            except Exception as e:
                self.logger.warning(f"Could not read output files for preview: {str(e)}")

            return {
                "status": "completed",
                "message": "Bank UAT testing completed successfully",
                "result": {
                    "bank_name": state["bank_name"],
                    "encryption_type": state["encryption_type"],
                    "generate_encrypted_curls": state["generate_encrypted_curls"],
                    "total_tests_executed": state["uat_results"].get("execution_summary", {}).get("total_commands", 0),
                    "test_results": state["uat_results"].get("performance_metrics", {}),
                    "output_files": state["output_files"],
                    "file_contents": file_contents,
                    "encryption_metadata": {
                        "encryption_type": state["encryption_type"],
                        "public_key_loaded": bool(state["bank_public_cert_pem"]),
                        "private_key_loaded": bool(state["private_key_pem"]),
                        "aes_key_loaded": bool(state.get("aes_key")),
                        "keys_are_real": state["keys_are_real"],
                        "key_source": state["key_source"],
                        "crypto_validation": state["uat_results"].get("crypto_validation", {})
                    },
                    "ai_analysis_results": self._format_ai_analysis_results(state),
                    "execution_summary": state["uat_results"].get("execution_summary", {}),
                    "urls_extracted": len(state["extracted_urls"]),
                    "curl_commands_generated": len(state["generated_curls"])
                }
            }

        except Exception as e:
            self.logger.error(f"Bank UAT testing failed: {str(e)}")
            return {
                "status": "failed",
                "message": str(e)
            }

    def _validate_parameters(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Validate input parameters using the validator"""
        validated_params = BankUATValidator.validate_parameters(parameters)
        
        # Auto-correct key mapping if UI sends incorrect mapping
        # This handles the case where UI sends service keys instead of bank certificate
        validated_params = self._auto_correct_key_mapping(validated_params)
        
        return validated_params
    
    def _auto_correct_key_mapping(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Auto-correct key mapping based on filenames when UI sends incorrect mapping.
        
        Expected mapping:
        - Bank certificate (rbl_cert, bank_cert, etc.) -> bank_public_cert_path
        - Service/Partner private key (service_private, partner_private) -> private_key_path  
        - Service/Partner public key (service_public, partner_public) -> partner_public_key_path
        """
        try:
            # Handle legacy public_key_path parameter for backward compatibility
            legacy_public_key_path = params.get("public_key_path", "")
            bank_public_cert_path = params.get("bank_public_cert_path", "")
            private_key_path = params.get("private_key_path", "")
            partner_public_key_path = params.get("partner_public_key_path", "")
            
            # If legacy public_key_path is provided but bank_public_cert_path is not
            if legacy_public_key_path and not bank_public_cert_path:
                legacy_filename = legacy_public_key_path.lower()
                
                # Check if it's actually a service/partner public key (wrong mapping)
                if "service_public" in legacy_filename or "partner_public" in legacy_filename:
                    self.logger.warning("Detected legacy UI key mapping issue - auto-correcting...")
                    self.logger.warning(f"  Legacy public_key_path contains service/partner key: {legacy_public_key_path}")
                    
                    # Move to partner_public_key_path if not already set
                    if not partner_public_key_path:
                        params["partner_public_key_path"] = legacy_public_key_path
                        self.logger.info(f"  Moved to partner_public_key_path: {legacy_public_key_path}")
                    
                    # Remove legacy parameter
                    params.pop("public_key_path", None)
                    
                elif "bank" in legacy_filename or "rbl" in legacy_filename or "cert" in legacy_filename:
                    # Looks like a bank certificate - migrate to new parameter
                    params["bank_public_cert_path"] = legacy_public_key_path
                    params.pop("public_key_path", None)
                    self.logger.info(f"Migrated legacy public_key_path to bank_public_cert_path: {legacy_public_key_path}")
                else:
                    # Assume it's a bank certificate for backward compatibility
                    params["bank_public_cert_path"] = legacy_public_key_path
                    params.pop("public_key_path", None)
                    self.logger.info(f"Migrated legacy public_key_path to bank_public_cert_path (assumed bank cert): {legacy_public_key_path}")
            
            # Validate that we have the correct keys for encryption
            if params.get("generate_encrypted_curls", False):
                if not params.get("bank_public_cert_path"):
                    self.logger.error("MISSING BANK CERTIFICATE: Encryption enabled but no bank public certificate provided")
                    self.logger.error("Required: bank_public_cert_path parameter with bank's public certificate")
                    self.logger.error("Expected file: rbl_cert.pem, bank_cert.pem, or similar bank certificate file")
                    self.logger.error("Current parameters:")
                    self.logger.error(f"  bank_public_cert_path: {params.get('bank_public_cert_path', 'NOT PROVIDED')}")
                    self.logger.error(f"  private_key_path: {params.get('private_key_path', 'NOT PROVIDED')}")
                    self.logger.error(f"  partner_public_key_path: {params.get('partner_public_key_path', 'NOT PROVIDED')}")
            
            return params
            
        except Exception as e:
            self.logger.warning(f"Key mapping auto-correction failed: {str(e)}")
            return params

    def _load_api_documentation(self, state: BankUATState, ctx: Context) -> BankUATState:
        """Load and parse API documentation"""
        self.logger.info(f"Loading API documentation: {state['api_doc_path']}")

        try:
            # Log file path details for debugging
            file_path = state["api_doc_path"]
            self.logger.info(f"File Path Analysis:")
            self.logger.info(f"  Original path: {file_path}")
            self.logger.info(f"  Path exists: {os.path.exists(file_path)}")
            self.logger.info(f"  Is absolute: {os.path.isabs(file_path)}")

            # Check if file exists and get file info
            if os.path.exists(file_path):
                file_size = os.path.getsize(file_path)
                self.logger.info(f"  File size: {file_size} bytes")
            else:
                # Try multiple possible locations
                possible_paths = [
                    Path(__file__).parent.parent.parent.parent.parent / file_path,
                    # Look in bank_uat_agent specific directories
                    Path(
                        __file__).parent.parent.parent.parent.parent / "uploads" / "bank_uat_agent" / "documents" / Path(
                        file_path).name,
                    Path(__file__).parent.parent.parent.parent.parent / "uploads" / "bank_uat_agent" / "crypto" / Path(
                        file_path).name
                ]

                for path in possible_paths:
                    if path.exists():
                        file_path = str(path)
                        file_size = os.path.getsize(file_path)
                        self.logger.info(f"  Found file at: {file_path} (Size: {file_size} bytes)")
                        break
                else:
                    raise FileNotFoundError(f"API documentation file not found: {state['api_doc_path']}")

            # Resolve file path first
            resolved_file_path = self._resolve_file_path(file_path, "document")
            self.logger.info(f"  Resolved file path: {resolved_file_path}")

            with open(resolved_file_path, 'r', encoding='utf-8') as f:
                api_doc_content = f.read()

            content_length = len(api_doc_content)
            content_preview = api_doc_content[:250] if content_length > 0 else ""

            self.logger.info(f"Document Content Analysis:")
            self.logger.info(f"  Content preview: {content_preview}...")

            if not api_doc_content.strip():
                error_msg = f"API documentation file is empty: {state['api_doc_path']} (Size: {content_length} bytes)"
                self.logger.error(f"ERROR: {error_msg}")
                state["error_message"] = error_msg
                state["workflow_status"] = "error"
                return state

            state["api_doc_content"] = api_doc_content
            state["workflow_status"] = "success"
            self.logger.info(f"Successfully loaded API documentation: {content_length} characters")

        except FileNotFoundError as e:
            error_msg = f"API documentation file not found: {state['api_doc_path']}"
            self.logger.error(f"ERROR: {error_msg}")
            state["error_message"] = error_msg
            state["workflow_status"] = "error"
        except PermissionError as e:
            error_msg = f"Permission denied accessing file: {state['api_doc_path']}"
            self.logger.error(f"ERROR: {error_msg}")
            state["error_message"] = error_msg
            state["workflow_status"] = "error"
        except UnicodeDecodeError as e:
            error_msg = f"Unable to read file (encoding issue): {state['api_doc_path']}"
            self.logger.error(f"ERROR: {error_msg} - {str(e)}")
            state["error_message"] = error_msg
            state["workflow_status"] = "error"
        except Exception as e:
            self.logger.error(f"ERROR: Unexpected error loading API documentation: {str(e)}")
            state["error_message"] = str(e)
            state["workflow_status"] = "error"

        return state

    def _resolve_file_path(self, file_path: str, file_type: str = "document") -> str:
        """Resolve file path with fallback to bank_uat_agent directories"""
        try:
            # Try original path first
            if os.path.exists(file_path):
                return file_path

            # Try absolute path
            abs_path = os.path.abspath(file_path)
            if os.path.exists(abs_path):
                return abs_path

            # Try bank_uat_agent specific directories
            project_root = Path(__file__).resolve().parent.parent.parent.parent.parent
            filename = Path(file_path).name

            if file_type == "crypto":
                bank_crypto_path = project_root / "uploads" / "bank_uat_agent" / "crypto" / filename
                if bank_crypto_path.exists():
                    self.logger.info(f"Found crypto file in bank_uat_agent directory: {bank_crypto_path}")
                    return str(bank_crypto_path)

            if file_type == "document":
                bank_doc_path = project_root / "uploads" / "bank_uat_agent" / "documents" / filename
                if bank_doc_path.exists():
                    self.logger.info(f"Found document in bank_uat_agent directory: {bank_doc_path}")
                    return str(bank_doc_path)

            # Fallback to original path
            return file_path

        except Exception as e:
            self.logger.warning(f"Error resolving file path {file_path}: {str(e)}")
            return file_path

    def _extract_uat_host(self, state: BankUATState, ctx: Context) -> BankUATState:
        """Extract UAT host from documentation or use user-provided host"""
        self.logger.info("Starting UAT host extraction/validation step")

        try:
            # Extract UAT host from documentation ONLY if user hasn't provided one
            current_uat_host = state.get("uat_host", "")
            self.logger.info(f"UAT Host Check - Current state: '{current_uat_host}' (type: {type(current_uat_host)})")

            # Check if UAT host is provided and not empty
            if not str(current_uat_host).strip():
                self.logger.info("No UAT host provided by user, extracting from documentation")
                api_doc_content = state.get("api_doc_content", "")

                if not api_doc_content:
                    error_msg = "No API documentation content available for UAT host extraction"
                    self.logger.error(f"ERROR: {error_msg}")
                    state["error_message"] = error_msg
                    state["workflow_status"] = "error"
                    return state

                extracted_host = self._extract_uat_host_from_documentation(api_doc_content, ctx)
                if extracted_host:
                    self.logger.info(f"Extracted UAT host from documentation: {extracted_host}")
                    state["uat_host"] = extracted_host
                else:
                    error_msg = "No UAT host found in documentation and none provided by user. UAT host is required for API testing."
                    self.logger.error(f"ERROR: {error_msg}")
                    state["error_message"] = error_msg
                    state["workflow_status"] = "error"
                    return state
            else:
                self.logger.info(f"Using user-provided UAT host: '{str(current_uat_host).strip()}'")

            state["workflow_status"] = "success"
            self.logger.info(f"UAT host extraction/validation completed successfully")

        except Exception as e:
            error_msg = f"Error during UAT host extraction: {str(e)}"
            self.logger.error(f"ERROR: {error_msg}")
            state["error_message"] = error_msg
            state["workflow_status"] = "error"

        return state

    def _load_encryption_keys(self, state: BankUATState, ctx: Context) -> BankUATState:
        """
        Load encryption keys and certificates based on encryption type and requirements.
        Only processes keys when generate_encrypted_curls is true.
        
        Supports:
        - Bank public certificates (for encrypting data sent to bank)
        - Partner private keys (for signing requests and decrypting responses)
        - Partner public keys (for bank to encrypt responses)
        - AES keys (for symmetric encryption)
        """
        self.logger.info(f"Setting up encryption keys for {state['encryption_type']} encryption")

        try:
            # Early exit if encryption is not requested
            if not state["generate_encrypted_curls"]:
                self.logger.info("Encryption not requested (generate_encrypted_curls=false) - skipping key loading")
                state["bank_public_cert_pem"] = None
                state["private_key_pem"] = None
                state["aes_key"] = None
                state["keys_are_real"] = False
                state["key_source"] = "none"
                state["workflow_status"] = "success"
                return state

            # Determine key requirements based on encryption type
            key_requirements = self._determine_key_requirements(state["encryption_type"], state.get("final_encryption_config"))
            
            self.logger.info(f"Crypto Key Analysis:")
            self.logger.info(f"  Encryption type: {state['encryption_type']}")
            self.logger.info(f"  Generate encrypted curls: {state['generate_encrypted_curls']}")
            self.logger.info(f"  Required keys: {key_requirements}")
            
            # Check available key paths
            bank_cert_path = state.get("bank_public_cert_path")  # Bank's public certificate
            partner_private_key_path = state.get("private_key_path")  # Partner's private key
            partner_public_key_path = state.get("partner_public_key_path")  # Partner's public key (optional)
            aes_key = state.get("aes_key")  # AES key for symmetric encryption
            
            self.logger.info(f"  Bank certificate path: {bank_cert_path or 'Not provided'}")
            self.logger.info(f"  Partner private key path: {partner_private_key_path or 'Not provided'}")
            self.logger.info(f"  Partner public key path: {partner_public_key_path or 'Not provided'}")
            self.logger.info(f"  AES key provided: {'YES' if aes_key else 'NO'}")

            # Validate that required keys are provided
            validation_errors = self._validate_key_availability(key_requirements, bank_cert_path, 
                                                              partner_private_key_path, partner_public_key_path, aes_key)
            
            if validation_errors:
                error_msg = f"Missing required keys for {state['encryption_type']} encryption: {'; '.join(validation_errors)}"
                self.logger.error(f"ERROR: {error_msg}")
                state["error_message"] = error_msg
                state["workflow_status"] = "error"
                return state

            # Load Bank Certificate (Public Key for encryption)
            if bank_cert_path and key_requirements.get("requires_bank_cert", False):
                state = self._load_bank_certificate(state, bank_cert_path)
                if state["workflow_status"] == "error":
                    return state

            # Load Partner Private Key (For signing and decryption)
            if partner_private_key_path and key_requirements.get("requires_partner_private_key", False):
                state = self._load_partner_private_key(state, partner_private_key_path)
                if state["workflow_status"] == "error":
                    return state

            # Load Partner Public Key (Optional - for bank to encrypt responses)
            if partner_public_key_path and key_requirements.get("supports_partner_public_key", False):
                state = self._load_partner_public_key(state, partner_public_key_path)
                if state["workflow_status"] == "error":
                    return state

            # Handle AES Key
            if key_requirements.get("requires_aes_key", False):
                state = self._handle_aes_key(state, aes_key)
                if state["workflow_status"] == "error":
                    return state

            # Validate key compatibility based on encryption type
            state = self._validate_key_compatibility(state, key_requirements)
            if state["workflow_status"] == "error":
                return state

            # Mark keys as real and set metadata
            state["keys_are_real"] = True
            state["key_source"] = "provided"
            
            # Set key references for prompt usage (not actual key content)
            state["public_key_reference"] = "BANK_CERTIFICATE_PLACEHOLDER" if state.get("bank_public_cert_pem") else None
            state["private_key_reference"] = "PARTNER_PRIVATE_KEY_PLACEHOLDER" if state.get("private_key_pem") else None

            # Final crypto summary
            self.logger.info("Final Crypto Configuration Summary:")
            self.logger.info(f"  Bank certificate loaded: {'YES' if state.get('bank_public_cert_pem') else 'NO'}")
            self.logger.info(f"  Partner private key loaded: {'YES' if state.get('private_key_pem') else 'NO'}")
            self.logger.info(f"  Partner public key loaded: {'YES' if state.get('partner_public_key_pem') else 'NO'}")
            self.logger.info(f"  AES key available: {'YES' if state.get('aes_key') else 'NO'}")
            self.logger.info(f"  Keys are real: {'YES' if state['keys_are_real'] else 'NO (dummy)'}")
            self.logger.info(f"  Key source: {state['key_source']}")
            self.logger.info(f"  Encryption type: {state['encryption_type']}")

            state["workflow_status"] = "success"

        except FileNotFoundError as e:
            error_msg = f"Crypto key file not found: {str(e)}"
            self.logger.error(f"ERROR: {error_msg}")
            state["error_message"] = error_msg
            state["workflow_status"] = "error"
        except Exception as e:
            self.logger.error(f"ERROR: Error setting up encryption keys: {str(e)}")
            state["error_message"] = str(e)
            state["workflow_status"] = "error"

        return state

    def _determine_key_requirements(self, encryption_type: str, final_config: Optional[Any] = None) -> Dict[str, bool]:
        """Determine what keys are required based on encryption type"""
        requirements = {
            "requires_bank_cert": False,
            "requires_partner_private_key": False, 
            "supports_partner_public_key": False,
            "requires_aes_key": False
        }
        
        encryption_type = encryption_type.lower()
        
        if encryption_type in ["hybrid", "auto_detect"]:
            requirements["requires_bank_cert"] = True
            requirements["requires_partner_private_key"] = True
            requirements["supports_partner_public_key"] = True
            requirements["requires_aes_key"] = True
                
        elif encryption_type == "none":
            # No keys required
            pass
        
        # Override with final config if available
        if final_config and hasattr(final_config, 'algorithms'):
            if "RSA" in final_config.algorithms.key_encryption:
                requirements["requires_bank_cert"] = True
            if "AES" in final_config.algorithms.payload_encryption:
                requirements["requires_aes_key"] = True
            if final_config.algorithms.signature:
                requirements["requires_partner_private_key"] = True
                
        self.logger.info(f"Key requirements for {encryption_type}: {requirements}")
        return requirements

    def _validate_key_availability(self, requirements: Dict[str, bool], bank_cert_path: Optional[str], 
                                 partner_private_path: Optional[str], partner_public_path: Optional[str], 
                                 aes_key: Optional[str]) -> List[str]:
        """Validate that required keys are available"""
        errors = []
        
        if requirements["requires_bank_cert"] and not bank_cert_path:
            errors.append("Bank certificate (public_key_path or bank_public_cert_path) is REQUIRED for encryption")
            errors.append("Expected: Bank's public certificate file (e.g., rbl_cert.pem, bank_cert.pem)")
            errors.append("Current issue: UI may be sending service_public_key instead of bank certificate")
            
        if requirements["requires_partner_private_key"] and not partner_private_path:
            errors.append("Partner private key (private_key_path) is required")
            
        if requirements["requires_aes_key"] and not aes_key:
            self.logger.info("AES key not provided - will generate automatically")
            # Don't add to errors as AES key can be auto-generated
            
        return errors

    def _load_bank_certificate(self, state: BankUATState, cert_path: str) -> BankUATState:
        """Load bank's public certificate for encryption"""
        try:
            resolved_cert_path = self._resolve_file_path(cert_path, "crypto")
            self.logger.info(f"Loading bank certificate from: {resolved_cert_path}")

            if not os.path.exists(resolved_cert_path):
                raise FileNotFoundError(f"Bank certificate file not found: {resolved_cert_path}")

            file_size = os.path.getsize(resolved_cert_path)
            self.logger.info(f"  Certificate file size: {file_size} bytes")

            # Load certificate/public key
            state["bank_public_cert_pem"] = self.rsa_crypto.load_public_key(resolved_cert_path)

            # Analyze certificate format
            cert_content = state["bank_public_cert_pem"]
            if "BEGIN CERTIFICATE" in cert_content:
                self.logger.info(f"  Format: X.509 Certificate")
                cert_type = "X509_CERTIFICATE"
            elif "BEGIN PUBLIC KEY" in cert_content:
                self.logger.info(f"  Format: PEM Public Key")
                cert_type = "PEM_PUBLIC_KEY"
            elif "BEGIN RSA PUBLIC KEY" in cert_content:
                self.logger.info(f"  Format: RSA Public Key")
                cert_type = "RSA_PUBLIC_KEY"
            else:
                cert_type = "UNKNOWN"

            # Log certificate info (preview only)
            cert_preview = cert_content[:100].replace('\n', '\\n')
            self.logger.info(f"  SUCCESS: Bank certificate loaded successfully")
            self.logger.info(f"  Certificate type: {cert_type}")
            self.logger.info(f"  Certificate preview: {cert_preview}...")
            self.logger.info(f"  Certificate length: {len(cert_content)} characters")

        except Exception as e:
            error_msg = f"Failed to load bank certificate: {str(e)}"
            self.logger.error(f"ERROR: {error_msg}")
            state["error_message"] = error_msg
            state["workflow_status"] = "error"

        return state

    def _load_partner_private_key(self, state: BankUATState, key_path: str) -> BankUATState:
        """Load partner's private key for signing and decryption"""
        try:
            resolved_key_path = self._resolve_file_path(key_path, "crypto")
            self.logger.info(f"Loading partner private key from: {resolved_key_path}")

            if not os.path.exists(resolved_key_path):
                raise FileNotFoundError(f"Partner private key file not found: {resolved_key_path}")

            file_size = os.path.getsize(resolved_key_path)
            self.logger.info(f"  Private key file size: {file_size} bytes")

            # Load private key
            state["private_key_pem"] = self.rsa_crypto.load_private_key(resolved_key_path)

            # Analyze key format
            key_content = state["private_key_pem"]
            if "BEGIN PRIVATE KEY" in key_content:
                self.logger.info(f"  Format: PKCS#8 Private Key")
                key_format = "PKCS8"
            elif "BEGIN RSA PRIVATE KEY" in key_content:
                self.logger.info(f"  Format: PKCS#1 RSA Private Key")
                key_format = "PKCS1"
            elif "BEGIN ENCRYPTED PRIVATE KEY" in key_content:
                self.logger.info(f"  Format: Encrypted PKCS#8 Private Key")
                key_format = "ENCRYPTED_PKCS8"
            else:
                key_format = "UNKNOWN"

            # Log key info (preview only for security)
            key_preview = key_content[:100].replace('\n', '\\n')
            self.logger.info(f"  SUCCESS: Partner private key loaded successfully")
            self.logger.info(f"  Key format: {key_format}")
            self.logger.info(f"  Key preview: {key_preview}...")
            self.logger.info(f"  Key length: {len(key_content)} characters")

        except Exception as e:
            error_msg = f"Failed to load partner private key: {str(e)}"
            self.logger.error(f"ERROR: {error_msg}")
            state["error_message"] = error_msg
            state["workflow_status"] = "error"

        return state

    def _load_partner_public_key(self, state: BankUATState, key_path: str) -> BankUATState:
        """Load partner's public key (optional - for bank to encrypt responses)"""
        try:
            resolved_key_path = self._resolve_file_path(key_path, "crypto")
            self.logger.info(f"Loading partner public key from: {resolved_key_path}")

            if not os.path.exists(resolved_key_path):
                raise FileNotFoundError(f"Partner public key file not found: {resolved_key_path}")

            # Load public key
            partner_public_key = self.rsa_crypto.load_public_key(resolved_key_path)
            state["partner_public_key_pem"] = partner_public_key

            self.logger.info(f"  SUCCESS: Partner public key loaded successfully")
            self.logger.info(f"  Key length: {len(partner_public_key)} characters")

        except Exception as e:
            # Partner public key is optional, so log warning instead of error
            self.logger.warning(f"Could not load partner public key: {str(e)}")
            state["partner_public_key_pem"] = None

        return state

    def _handle_aes_key(self, state: BankUATState, aes_key: Optional[str]) -> BankUATState:
        """Handle AES key - use provided key or generate new one"""
        try:
            if aes_key:
                # Validate provided AES key
                if len(aes_key) not in [32, 48, 64]:  # 128, 192, 256 bit keys in hex
                    raise ValueError(f"Invalid AES key length: {len(aes_key)} characters. Expected 32 (128-bit), 48 (192-bit), or 64 (256-bit) hex characters")
                
                # Validate hex format
                try:
                    int(aes_key, 16)
                except ValueError:
                    raise ValueError("AES key must be in hexadecimal format")
                
                state["aes_key"] = aes_key
                key_bits = len(aes_key) * 4
                self.logger.info(f"  SUCCESS: Using provided AES-{key_bits} key")
                
            else:
                # Generate new AES key
                import secrets
                aes_key = secrets.token_hex(32)  # 256-bit key
                state["aes_key"] = aes_key
                self.logger.info(f"  SUCCESS: Generated new AES-256 key")

            self.logger.info(f"  AES key preview: {state['aes_key'][:8]}...{state['aes_key'][-8:]}")

        except Exception as e:
            error_msg = f"Failed to handle AES key: {str(e)}"
            self.logger.error(f"ERROR: {error_msg}")
            state["error_message"] = error_msg
            state["workflow_status"] = "error"

        return state

    def _validate_key_compatibility(self, state: BankUATState, requirements: Dict[str, bool]) -> BankUATState:
        """Validate that loaded keys are compatible with each other and encryption type"""
        try:
            # Validate RSA key pair if both public and private keys are loaded
            if (state.get("bank_public_cert_pem") and state.get("private_key_pem") and 
                requirements.get("requires_bank_cert") and requirements.get("requires_partner_private_key")):
                
                self.logger.info("Validating bank certificate and partner private key compatibility...")
                
                # Note: Bank cert and partner private key are typically NOT a matching pair
                # They serve different purposes:
                # - Bank cert: Used to encrypt data sent TO the bank
                # - Partner private key: Used to sign requests and decrypt responses FROM the bank
                
                # Validate individual key formats
                if not self.rsa_crypto._is_valid_public_key(state["bank_public_cert_pem"]):
                    raise ValueError("Invalid bank certificate format")
                    
                if not self.rsa_crypto._is_valid_private_key(state["private_key_pem"]):
                    raise ValueError("Invalid partner private key format")
                
                self.logger.info("  SUCCESS: Bank certificate and partner private key formats are valid")
                self.logger.info("  NOTE: These keys serve different purposes and are not expected to be a matching pair")

            # Validate partner key pair if both partner keys are loaded
            if state.get("partner_public_key_pem") and state.get("private_key_pem"):
                self.logger.info("Validating partner public/private key pair...")
                is_valid = self.rsa_crypto.validate_rsa_keys(state["partner_public_key_pem"], state["private_key_pem"])
                if not is_valid:
                    self.logger.warning("WARNING: Partner public/private key pair validation failed")
                    self.logger.warning("  Partner keys should form a matching pair for proper encryption/decryption")
                else:
                    self.logger.info("  SUCCESS: Partner key pair validation successful")

            # Validate AES key if required
            if requirements.get("requires_aes_key") and state.get("aes_key"):
                aes_key = state["aes_key"]
                if len(aes_key) not in [32, 48, 64]:
                    raise ValueError(f"Invalid AES key length: {len(aes_key)} characters")
                self.logger.info(f"  SUCCESS: AES key validation passed (AES-{len(aes_key)*4})")

            self.logger.info("Key compatibility validation completed successfully")

        except Exception as e:
            error_msg = f"Key compatibility validation failed: {str(e)}"
            self.logger.error(f"ERROR: {error_msg}")
            state["error_message"] = error_msg
            state["workflow_status"] = "error"

        return state

    def _determine_actual_encryption_type(self, config: Any) -> str:
        """Determine the actual encryption type from template configuration"""
        try:
            # Check the algorithms to determine actual encryption type
            if hasattr(config, 'algorithms'):
                key_encryption = getattr(config.algorithms, 'key_encryption', '').upper()
                payload_encryption = getattr(config.algorithms, 'payload_encryption', '').upper()
                signature = getattr(config.algorithms, 'signature', '')
                
                # Determine type based on algorithms used
                has_rsa = 'RSA' in key_encryption
                has_aes = 'AES' in payload_encryption
                has_signature = bool(signature)
                
                if has_rsa and has_aes:
                    return "hybrid"  # RSA + AES
                elif has_rsa and not has_aes:
                    return "rsa"     # Pure RSA
                elif has_aes and not has_rsa:
                    return "aes"     # Pure AES
                elif has_signature and not (has_rsa or has_aes):
                    return "signature_only"  # Signature only
                elif has_rsa:
                    return "rsa"     # Fallback to RSA
                    
            # Check placement strategy for additional clues
            if hasattr(config, 'placement_strategy'):
                placement = getattr(config, 'placement_strategy', '').lower()
                if placement == 'none':
                    return "none"
            
            # Default fallback based on common template patterns
            return "hybrid"  # Most bank templates use RSA+AES
            
        except Exception as e:
            self.logger.warning(f"Could not determine encryption type from config: {str(e)}")
            return "hybrid"  # Safe default for most bank integrations

    def _extract_api_urls(self, state: BankUATState, ctx: Context) -> BankUATState:
        """Extract API URLs from documentation using the UAT host from state"""
        self.logger.info(f"Extracting API URLs for {state['bank_name']} using UAT host from state")

        try:
            # Use UAT host that was already extracted in _extract_uat_host
            uat_host = state.get("uat_host")
            if not uat_host:
                state[
                    "error_message"] = "UAT host not available. Please provide uat_host parameter or ensure it can be extracted from documentation."
                state["workflow_status"] = "error"
                return state

            self.logger.info(f"Using UAT host from state: {uat_host}")

            extracted_urls = self.curl_generator.extract_urls_from_documentation(
                api_doc_content=state["api_doc_content"],
                bank_name=state["bank_name"],
                uat_host=uat_host,
                apis_to_test=None,
                ctx=ctx
            )

            if not extracted_urls:
                state["error_message"] = "No API URLs extracted from documentation"
                state["workflow_status"] = "error"
                return state

            state["extracted_urls"] = extracted_urls
            state["workflow_status"] = "success"
            self.logger.info(f"Successfully extracted {len(extracted_urls)} URLs")

        except Exception as e:
            self.logger.error(f"Error extracting API URLs: {str(e)}")
            state["error_message"] = str(e)
            state["workflow_status"] = "error"

        return state

    def _generate_curl_commands(self, state: BankUATState, ctx: Context) -> BankUATState:
        """Generate curl commands for UAT testing with conditional encryption"""
        self.logger.info(f"Generating curl commands for {len(state['extracted_urls'])} URLs")

        try:
            # Determine if encryption should be applied based on:
            # 1. User preference (generate_encrypted_curls)
            # 2. Encryption type is not 'none'
            # Note: Keys will be validated later in _load_encryption_keys
            should_use_encryption = (
                    state["generate_encrypted_curls"] and
                    state["encryption_type"].lower() != "none"
            )

            # Prepare encryption context for curl generation (use references, not actual keys)
            encryption_context = {
                "encryption_type": state["encryption_type"],
                "generate_encrypted_curls": state["generate_encrypted_curls"],
                "should_use_encryption": should_use_encryption,
                "public_key_reference": state["public_key_reference"],
                "private_key_reference": state["private_key_reference"],
                "keys_are_real": state["keys_are_real"],
                "key_source": state["key_source"]
            }

            generated_curls = self.curl_generator.generate_curl_commands(
                urls=state["extracted_urls"],
                api_doc_content=state["api_doc_content"],
                bank_name=state["bank_name"],
                custom_headers=state["custom_headers"],
                custom_prompt=state["custom_prompt"],
                encryption_context=encryption_context,
                ctx=ctx
            )

            if not generated_curls:
                state["error_message"] = "No curl commands generated"
                state["workflow_status"] = "error"
                return state

            state["generated_curls"] = generated_curls
            state["workflow_status"] = "success"
            self.logger.info(f"Successfully generated {len(generated_curls)} curl commands")

            # Log all generated curl commands for debugging
            self.logger.info("Generated cURL commands:")
            for i, curl_cmd in enumerate(generated_curls, 1):
                self.logger.raw_info(f"Curl Command {i}: {curl_cmd}")

        except Exception as e:
            self.logger.error(f"Error generating curl commands: {str(e)}")
            state["error_message"] = str(e)
            state["workflow_status"] = "error"

        return state

    def _execute_uat_tests(self, state: BankUATState, ctx: Context) -> BankUATState:
        """Execute UAT tests using the generated curl commands"""
        self.logger.info(f"Executing UAT tests for {state['bank_name']}")

        try:
            uat_results = self.uat_executor.execute_uat_tests(
                curl_commands=state["generated_curls"],
                bank_name=state["bank_name"],
                encryption_type=state["encryption_type"],
                bank_public_cert_pem=state["bank_public_cert_pem"],
                private_key_pem=state["private_key_pem"],
                partner_public_key_pem=state["partner_public_key_pem"],
                aes_key=state.get("aes_key"),
                timeout_seconds=state["timeout_seconds"],
                include_response_analysis=state["include_response_analysis"],
                custom_headers=state["custom_headers"],
                generate_encrypted_curls=state["generate_encrypted_curls"],
                final_encryption_config=state.get("final_encryption_config"),  # Pass template config
                ctx=ctx
            )

            state["uat_results"] = uat_results
            state["workflow_status"] = "success"

            # Log execution summary
            summary = uat_results.get("execution_summary", {})
            metrics = uat_results.get("performance_metrics", {})
            self.logger.info(
                f"UAT execution completed: {summary.get('total_commands', 0)} tests in {summary.get('execution_time_seconds', 0)}s")
            self.logger.info(f"Success rate: {metrics.get('success_rate', 0)}%")

        except Exception as e:
            self.logger.error(f"Error executing UAT tests: {str(e)}")
            state["error_message"] = str(e)
            state["workflow_status"] = "error"

        return state

    def _save_results(self, state: BankUATState, ctx: Context) -> BankUATState:
        """Save UAT results to files"""
        self.logger.info("Saving UAT results to files")

        try:
            # Get task_id from context
            task_id = self.get_task_id(ctx)

            # Save results using UAT executor
            output_files = self.uat_executor.save_results_to_file(
                results=state["uat_results"],
                output_dir=self.outputs_dir,
                bank_name=state["bank_name"],
                task_id=task_id
            )

            # Save curl commands separately with task_id format
            curl_filename = f"curl_commands_{task_id}.txt"
            curl_path = self.outputs_dir / curl_filename

            with open(curl_path, 'w', encoding='utf-8') as f:
                f.write(f"# Generated Curl Commands for {state['bank_name']}\n")
                f.write(f"# Task ID: {task_id}\n")
                f.write(f"# Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"# UAT Host: {state['uat_host']}\n")
                f.write(f"# Encryption Type: {state['encryption_type']}\n")
                f.write(f"# Generate Encrypted Curls: {state['generate_encrypted_curls']}\n")
                f.write(f"# Key Source: {state['key_source']}\n")
                f.write(f"# Keys are Real: {state['keys_are_real']}\n")

                for i, curl_cmd in enumerate(state["generated_curls"], 1):
                    f.write(f"# Command {i}\n{curl_cmd}\n\n")

            output_files["curl_commands"] = str(curl_path)

            state["output_files"] = output_files
            state["workflow_status"] = "success"
            self.logger.info(f"Results saved: {len(output_files)} files created")

        except Exception as e:
            self.logger.error(f"Error saving results: {str(e)}")
            state["error_message"] = str(e)
            state["workflow_status"] = "error"

        return state

    def _create_error_result(self, state: BankUATState) -> Dict[str, Any]:
        """Create error result from state"""
        return {
            "status": "failed",
            "message": state.get("error_message", "Unknown error occurred"),
            "result": {
                "bank_name": state.get("bank_name", ""),
                "uat_host": state.get("uat_host", ""),
                "encryption_type": state.get("encryption_type", ""),
                "generate_encrypted_curls": state.get("generate_encrypted_curls", False),
                "workflow_stage": state.get("workflow_status", "unknown"),
                "partial_results": {
                    "api_doc_loaded": bool(state.get("api_doc_content")),
                    "keys_loaded": bool(
                        state.get("bank_public_cert_pem") or state.get("private_key_pem") or state.get("aes_key")),
                    "keys_are_real": state.get("keys_are_real", False),
                    "key_source": state.get("key_source", "unknown"),
                    "urls_extracted": len(state.get("extracted_urls", {})),
                    "curls_generated": len(state.get("generated_curls", [])),
                    "tests_executed": bool(state.get("uat_results"))
                }
            }
        }

    def upload_key_file(self, file_content: bytes, filename: str, key_type: str) -> str:
        """
        Upload and save encryption key file
        
        Args:
            file_content: File content as bytes
            filename: Original filename
            key_type: "public" or "private"
            
        Returns:
            Path to saved file
        """
        try:
            # Validate file extension
            allowed_extensions = ['.pem', '.key', '.crt', '.txt']
            file_ext = Path(filename).suffix.lower()

            if file_ext not in allowed_extensions:
                raise ValueError(f"Invalid key file extension: {file_ext}. Allowed: {allowed_extensions}")

            # Create filename with timestamp
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            safe_filename = f"{key_type}_key_{timestamp}_{filename}"

            # Save to temp directory
            key_path = self.temp_dir / safe_filename

            with open(key_path, 'wb') as f:
                f.write(file_content)

            # Validate key format
            if key_type == "public":
                self.rsa_crypto.load_public_key(str(key_path))
            elif key_type == "private":
                self.rsa_crypto.load_private_key(str(key_path))

            self.logger.info(f"Successfully uploaded and validated {key_type} key: {key_path}")
            return str(key_path)

        except Exception as e:
            self.logger.error(f"Failed to upload {key_type} key file: {str(e)}")
            raise Exception(f"Key file upload failed: {str(e)}")

    def get_encryption_status(self) -> Dict[str, Any]:
        """Get status of encryption libraries and capabilities"""
        return {
            "rsa_available": self.rsa_crypto.check_availability(),
            "aes_available": self.aes_crypto.check_availability(),
            "supported_types": ["rsa", "aes", "hybrid", "none"],
            "key_formats": [".pem", ".key", ".crt", ".txt"],
            "recommendations": {
                "rsa": "Best for small payloads with high security requirements",
                "aes": "Fast encryption, compatible with legacy systems",
                "hybrid": "Combines RSA security with AES performance for large payloads",
                "none": "For testing without encryption"
            }
        }

    def _extract_uat_host_from_documentation(self, api_doc_content: str, ctx: Context) -> str:
        """Extract UAT host from API documentation content using autonomous agent"""
        self.logger.info("Extracting UAT host from API documentation content using AI")

        try:
            # Use autonomous agent to find UAT host from documentation
            self.logger.info("DEBUG: About to call _extract_host_using_ai")
            extracted_host = self._extract_host_using_ai(api_doc_content, ctx)
            self.logger.info(f"DEBUG: _extract_host_using_ai returned: '{extracted_host}'")

            if extracted_host:
                self.logger.info(f"AI successfully extracted UAT host: {extracted_host}")
                return extracted_host
            else:
                self.logger.warning("AI could not extract UAT host from documentation")
                return ""

        except Exception as e:
            self.logger.error(f"Error in AI-based UAT host extraction: {str(e)}")
            return ""

    def _extract_host_using_ai(self, api_doc_content: str, ctx: Context) -> str:
        """
        Extract UAT host using autonomous agent analysis of the API documentation
        
        Args:
            api_doc_content: The API documentation content to analyze
            ctx: Context for autonomous agent calls
            
        Returns:
            Extracted UAT host URL or empty string if not found
        """
        self.logger.info("DEBUG: _extract_host_using_ai method called")
        self.logger.info(f"DEBUG: api_doc_content length: {len(api_doc_content) if api_doc_content else 0}")
        self.logger.info(f"DEBUG: ctx type: {type(ctx)}")

        try:
            self.logger.info("Using autonomous agent to extract UAT host from documentation")

            # Create focused prompt for UAT host extraction
            prompt = f"""
  Extract the UAT host/base URL from the API documentation.
  Look for ANY URL that could be used for testing, including:
  1. URLs containing: uat, dev, test, staging, sandbox, demo
  2. Base URLs from API endpoints (extract the protocol + domain portion)
  3. Example URLs in code samples or cURL commands
  4. Any URL that appears to be for non-production use
  5. URLs with non-standard ports (like :8080, :8081, etc.)
  6. localhost or 127.0.0.1 addresses

  When you find an API endpoint like "POST /api/ OR GET /v1/", extract the base URL from any complete URL examples.

  If you find a complete URL like "https://api.yesbank.in/pobo/api/merchant-onboarding", return the base URL: "https://api.yesbank.in"

  Strictly Return ONLY the complete base URL (with protocol, eg https://uat.bank.com), or "NOT_FOUND" if no testable URL is available.

  Examples of valid responses:
  - https://uat.bank.com
  - https://api.sbi.in
  - http://127.0.0.1:8081
  - https://test-api.bank.com
  - NOT_FOUND

  API Documentation:
  {api_doc_content}
"""

            # Call autonomous agent
            agent_result = self._call_autonomous_agent(prompt, ctx)
            self.logger.info(
                f"Agent result keys: {list(agent_result.keys()) if isinstance(agent_result, dict) else 'Not a dict'}")
            self.logger.info(f"Agent result success: {agent_result.get('success', False)}")

            if agent_result.get("success", False):
                response_content = agent_result.get("result", "")
                self.logger.info(f"Raw AI response: {response_content}")
                self.logger.info(f"Raw AI response type: {type(response_content)}")

                # Handle nested content structure
                if isinstance(response_content, dict):
                    if "result" in response_content:
                        response_content = response_content["result"]
                        self.logger.info(f"Extracted 'result' field: {response_content}")
                    elif "content" in response_content:
                        response_content = response_content["content"]
                        self.logger.info(f"Extracted 'content' field: {response_content}")

                # Ensure we have a string before calling strip()
                if not isinstance(response_content, str):
                    response_content = str(response_content)
                    self.logger.info(f"Converted to string: {response_content}")

                response_content = response_content.strip()

                # Check if we got a valid response (avoid common "not found" variations)
                upper_content = response_content.upper()
                not_found_indicators = ["NOT_FOUND", "NOT FOUND", "NO URL", "NO HOST", "NONE", "N/A"]
                has_not_found = any(indicator in upper_content for indicator in not_found_indicators)

                self.logger.info(f"Response content check - has_not_found: {has_not_found}")
                if has_not_found:
                    matched_indicators = [ind for ind in not_found_indicators if ind in upper_content]
                    self.logger.info(f"Found 'not found' indicators: {matched_indicators}")

                if response_content and not has_not_found:
                    # Use regex to extract only the base URL (host) from the response
                    # Pattern matches protocol + domain + optional port, excludes paths
                    url_pattern = r'https?://[a-zA-Z0-9.-]+(?::[0-9]+)?'
                    url_match = re.search(url_pattern, response_content)
                    self.logger.info(f"Regex search result: {url_match.group(0) if url_match else 'No match'}")

                    if url_match:
                        base_url = url_match.group(0)
                        # Clean up any trailing punctuation that might be included
                        base_url = re.sub(r'[.,;:!?/]+$', '', base_url)
                        # Ensure clean base URL (no trailing slash)
                        base_url = base_url.rstrip('/')
                        self.logger.info(f"AI successfully extracted UAT base host using regex: {base_url}")
                        return base_url
                    else:
                        self.logger.warning(f"AI response doesn't contain a valid URL: {response_content}")
                        return ""
                else:
                    self.logger.info("AI indicated no UAT host found in documentation")
                    return ""
            else:
                error_msg = agent_result.get('error', 'Unknown error')
                self.logger.warning(f"AI UAT host extraction failed: {error_msg}")
                return ""

        except Exception as e:
            self.logger.error(f"AI host extraction failed with exception: {str(e)}")
            self.logger.error(f"Exception type: {type(e)}")
            if hasattr(e, '__traceback__'):
                import traceback
                self.logger.error(f"Traceback: {traceback.format_exc()}")
            return ""

    def _call_autonomous_agent(self, prompt: str, ctx: Context) -> Dict[str, Any]:
        """Call autonomous agent with the given prompt"""
        try:
            from src.agents.autonomous_agent import AutonomousAgentTool

            agent_tool = AutonomousAgentTool()
            result = agent_tool.execute({
                "prompt": prompt,
                "task_id": ctx.get("task_id", "uat-host-extraction"),
                "agent_name": "bank-uat-agent",
            })

            return result

        except Exception as e:
            self.logger.error(f"Autonomous agent execution failed: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "result": None
            }

    # AI-Powered Analysis Methods

    def _ai_analyze_encryption(self, state: BankUATState, ctx: Context) -> BankUATState:
        """AI-powered analysis of encryption requirements from documentation"""
        try:
            self.logger.info("Starting AI encryption analysis", extra={
                "bank_name": state["bank_name"],
                "doc_length": len(state["api_doc_content"]),
                "encryption_type": state["encryption_type"]
            })

            # Validate prerequisites
            if not state["api_doc_content"]:
                raise ValueError("API documentation content is required for AI analysis")

            # Perform AI analysis - handle event loop properly
            try:
                # Try to get existing event loop
                loop = asyncio.get_running_loop()
                # If there's a running loop, we need to run in a thread
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(
                        asyncio.run,
                        self.crypto_analyzer.analyze_encryption_requirements(
                            api_doc_content=state["api_doc_content"],
                            bank_name=state["bank_name"],
                            ctx=ctx
                        )
                    )
                    ai_config = future.result()
            except RuntimeError:
                # No running event loop, safe to use asyncio.run()
                ai_config = asyncio.run(self.crypto_analyzer.analyze_encryption_requirements(
                    api_doc_content=state["api_doc_content"],
                    bank_name=state["bank_name"],
                    ctx=ctx
                ))

            state["ai_extracted_config"] = ai_config

            # Get template recommendations (no bank-specific hardcoding)
            recommendations = self.template_recommender.recommend_templates(
                bank_name=state["bank_name"],
                detected_patterns=ai_config.detected_patterns,
                config=ai_config.extracted_config,
                context={"use_case": "bank_api_integration"}
            )

            state["template_recommendations"] = recommendations

            # Determine final configuration
            final_config = self._determine_final_configuration(state, ai_config)
            state["final_encryption_config"] = final_config

            # Update encryption type based on AI analysis only if auto-detect
            if state["encryption_type"] == "auto_detect":
                if final_config.template_name:
                    # Determine actual encryption type from the template-based config
                    actual_type = self._determine_actual_encryption_type(final_config)
                    state["encryption_type"] = actual_type
                    self.logger.info(f"AI detected template: {final_config.template_name}, actual type: {actual_type}")
                else:
                    state["encryption_type"] = final_config.encryption_type
                    self.logger.info(f"AI detected encryption type: {final_config.encryption_type}")

            self.logger.info(
                "AI encryption analysis completed",
                extra={
                    "confidence_score": ai_config.confidence_score,
                    "detected_patterns": ai_config.detected_patterns,
                    "final_encryption_type": state["encryption_type"],
                    "template_name": final_config.template_name,
                    "meets_threshold": ai_config.confidence_score >= state["ai_confidence_threshold"]
                }
            )

            state["workflow_status"] = "ai_analysis_completed"
            return state

        except Exception as e:
            self.logger.error(f"AI encryption analysis failed: {str(e)}")
            # Fail the workflow instead of using fallback
            state["workflow_status"] = "ai_analysis_failed"
            state["error_message"] = f"AI analysis failed: {str(e)}"
            return state

    async def _validate_crypto_configuration(self, state: BankUATState, ctx: Context) -> BankUATState:
        """Validate AI-extracted configuration and provide recommendations"""
        try:
            # Skip validation if AI analysis failed or was skipped
            if state["workflow_status"] == "ai_analysis_failed":
                self.logger.info("Skipping validation - AI analysis failed")
                state["workflow_status"] = "validation_skipped"
                return state

            if not state["ai_extracted_config"]:
                self.logger.warning("No AI-extracted config available for validation - skipping")
                state["workflow_status"] = "validation_skipped"
                return state

            self.logger.info("Validating AI-extracted configuration")

            # Perform validation
            validation_report = await self.ai_validator.validate_extracted_config(
                extracted_config=state["ai_extracted_config"],
                original_documentation=state["api_doc_content"],
                ctx=ctx
            )

            # Convert validation report to dict for state storage
            state["ai_validation_report"] = {
                "is_valid": validation_report.is_valid,
                "confidence_assessment": validation_report.confidence_assessment,
                "issues": [
                    {
                        "severity": issue.severity,
                        "category": issue.category,
                        "message": issue.message,
                        "suggestion": issue.suggestion,
                        "auto_fixable": issue.auto_fixable
                    } for issue in validation_report.issues
                ],
                "suggestions": validation_report.suggestions,
                "recommended_actions": validation_report.recommended_actions,
                "compatibility_score": validation_report.compatibility_score,
                "template_alternatives": validation_report.template_alternatives
            }

            # Check if configuration meets confidence threshold
            if state["ai_extracted_config"].confidence_score < state["ai_confidence_threshold"]:
                self.logger.warning(
                    f"AI confidence ({state['ai_extracted_config'].confidence_score:.2f}) below threshold ({state['ai_confidence_threshold']})"
                )

                # Add recommendation to review configuration
                state["ai_validation_report"]["suggestions"].append(
                    f"AI confidence ({state['ai_extracted_config'].confidence_score:.2f}) is below threshold ({state['ai_confidence_threshold']}) - manual review recommended"
                )

            # Check for critical issues
            critical_issues = [
                issue for issue in validation_report.issues
                if issue.severity == "critical"
            ]

            if critical_issues:
                self.logger.warning(f"Found {len(critical_issues)} critical configuration issues")
                state["ai_validation_report"]["has_critical_issues"] = True
                # Continue workflow but flag issues
            else:
                state["ai_validation_report"]["has_critical_issues"] = False

            self.logger.info(
                "Configuration validation completed",
                extra={
                    "is_valid": validation_report.is_valid,
                    "issues_count": len(validation_report.issues),
                    "critical_issues": len(critical_issues),
                    "compatibility_score": validation_report.compatibility_score,
                    "meets_threshold": state["ai_extracted_config"].confidence_score >= state["ai_confidence_threshold"]
                }
            )

            state["workflow_status"] = "validation_completed"
            return state

        except Exception as e:
            self.logger.error(f"Configuration validation failed: {str(e)}")
            # Don't fail workflow - continue with warning
            state["workflow_status"] = "validation_failed"
            state["error_message"] = f"Validation failed: {str(e)} - continuing without validation"

            # Create basic validation report indicating failure
            state["ai_validation_report"] = {
                "is_valid": False,
                "confidence_assessment": "ERROR - Validation failed",
                "issues": [{
                    "severity": "critical",
                    "category": "validation",
                    "message": f"Validation error: {str(e)}",
                    "suggestion": "Manual review required"
                }],
                "suggestions": ["Validation failed - manual configuration review recommended"],
                "recommended_actions": ["Verify configuration manually", "Test with sample requests"],
                "compatibility_score": 0.0
            }

            return state

    def _determine_final_configuration(self, state: BankUATState, ai_config: AIExtractedConfig) -> EncryptionConfig:
        """Determine final configuration based on AI analysis and user overrides"""

        # Start with AI-extracted configuration
        final_config = ai_config.extracted_config

        # Apply manual overrides if provided
        if state["manual_config_override"]:
            self.logger.info("Applying manual configuration overrides")

            override_data = state["manual_config_override"]

            # Update specific fields if provided
            if "encryption_type" in override_data:
                final_config.encryption_type = override_data["encryption_type"]

            if "template_name" in override_data:
                final_config.template_name = override_data["template_name"]

            if "placement_strategy" in override_data:
                final_config.placement_strategy = override_data["placement_strategy"]

            if "algorithms" in override_data:
                # Update algorithm settings
                algo_override = override_data["algorithms"]
                if "key_encryption" in algo_override:
                    final_config.algorithms.key_encryption = algo_override["key_encryption"]
                if "payload_encryption" in algo_override:
                    final_config.algorithms.payload_encryption = algo_override["payload_encryption"]
                if "signature" in algo_override:
                    final_config.algorithms.signature = algo_override["signature"]

            if "crypto_keys" in override_data:
                # Update key settings
                keys_override = override_data["crypto_keys"]
                if "bank_public_cert_path" in keys_override:
                    final_config.crypto_keys.bank_public_cert_path = keys_override["bank_public_cert_path"]
                if "partner_private_key_path" in keys_override:
                    final_config.crypto_keys.partner_private_key_path = keys_override["partner_private_key_path"]
                if "partner_id" in keys_override:
                    final_config.crypto_keys.partner_id = keys_override["partner_id"]

        # Set key paths from state if available
        if state["bank_public_cert_path"]:
            final_config.crypto_keys.bank_public_cert_path = state["bank_public_cert_path"]
        if state["private_key_path"]:
            final_config.crypto_keys.partner_private_key_path = state["private_key_path"]

        return final_config

    def _determine_execution_path(self, state: BankUATState) -> str:
        """Determine the execution path based on template, keys, and encryption flag"""

        # Check if encryption is enabled
        encryption_enabled = state["generate_encrypted_curls"]

        # Check if template is provided
        template_provided = bool(state.get("encryption_template"))

        # Check if keys are provided (both public and private)
        keys_provided = bool(
            state.get("bank_public_cert_path") and
            state.get("private_key_path")
        )

        self.logger.info("Execution path determination", extra={
            "encryption_enabled": encryption_enabled,
            "template_provided": template_provided,
            "keys_provided": keys_provided,
            "template": state.get("encryption_template"),
            "bank_public_cert_path": state.get("bank_public_cert_path"),
            "private_key_path": state.get("private_key_path")
        })

        # Decision logic based on your requirements:
        # Case 1: generate_encrypted_curls=true + template + keys -> full execution
        # Case 2: generate_encrypted_curls=false OR (no template AND no keys) -> AI config generation
        # Case 3: Other cases -> no encryption

        if encryption_enabled and template_provided and keys_provided:
            # All required components present - continue with full execution
            return "full_execution"
        elif not encryption_enabled or (not template_provided and not keys_provided):
            # Need AI to generate config for user download
            return "config_generation"
        else:
            # Partial components - no encryption
            return "no_encryption"

    def _apply_template_configuration(self, state: BankUATState, ctx: Context) -> BankUATState:
        """Apply the provided template configuration"""
        try:
            self.logger.info(f"Applying encryption template: {state['encryption_template']}")

            # Import template utilities
            from .config import get_template_by_name, create_config_from_template

            # Get the template
            template = get_template_by_name(state["encryption_template"])
            if not template:
                raise ValueError(f"Template '{state['encryption_template']}' not found")

            # Create configuration from template
            config = create_config_from_template(
                template_name=state["encryption_template"],
                overrides=state.get("manual_config_override", {})
            )

            # Store the final configuration
            state["final_encryption_config"] = config
            
            # Extract the actual encryption type from the template config
            actual_encryption_type = self._determine_actual_encryption_type(config)
            
            # Only override encryption_type if it was auto_detect, preserve user's explicit choice
            if state["encryption_type"] == "auto_detect":
                state["encryption_type"] = actual_encryption_type
            else:
                self.logger.info(f"Preserving user-specified encryption type: {state['encryption_type']} (template would suggest: {actual_encryption_type})")

            self.logger.info("Template configuration applied successfully", extra={
                "template_name": state["encryption_template"],
                "template_encryption_type": config.encryption_type,
                "actual_encryption_type": actual_encryption_type,
                "placement_strategy": config.placement_strategy
            })

            state["workflow_status"] = "template_applied"
            return state

        except Exception as e:
            self.logger.error(f"Failed to apply template configuration: {str(e)}")
            state["workflow_status"] = "error"
            state["error_message"] = f"Template application failed: {str(e)}"
            return state

    def _generate_encryption_config_for_download(self, state: BankUATState, ctx: Context) -> BankUATState:
        """Generate encryption configuration using AI and prepare for download"""
        self.logger.info("Generating encryption configuration for download")

        # Perform AI analysis to generate config
        if state["enable_ai_analysis"] and state["api_doc_content"]:
            state = self._ai_analyze_encryption(state, ctx)

            # If AI analysis succeeded, use that config
            if state["workflow_status"] == "ai_analysis_completed" and state.get("final_encryption_config"):
                self.logger.info("AI successfully generated encryption configuration")
                state["workflow_status"] = "completed"
                return state
            else:
                # AI analysis failed - throw error instead of fallback
                error_msg = "AI encryption analysis failed and no manual configuration provided"
                self.logger.error(error_msg)
                state["workflow_status"] = "error"
                state["error_message"] = error_msg
                return state
        else:
            # AI analysis disabled or no documentation - throw error instead of fallback
            error_msg = "AI analysis is disabled or no API documentation provided. Cannot generate encryption configuration without input."
            self.logger.error(error_msg)
            state["workflow_status"] = "error"
            state["error_message"] = error_msg
            return state

    def _create_config_generation_result(self, state: BankUATState, ctx: Context) -> Dict[str, Any]:
        """Create result for config generation workflow (ends here for user download)"""

        # Generate downloadable configuration file
        config_data = self._format_config_for_download(state, ctx)

        return {
            "status": "completed",
            "message": "Encryption configuration generated successfully - ready for download",
            "result": {
                "bank_name": state["bank_name"],
                "workflow_type": "config_generation",
                "configuration_completed": True,
                "ai_analysis_performed": state.get("ai_extracted_config") is not None,
                "configuration": config_data,
                "download_instructions": {
                    "description": "Download the generated encryption configuration",
                    "filename": f"{state['bank_name']}_encryption_config.json",
                    "usage": "Use this configuration file for future UAT executions with encryption"
                },
                "next_steps": [
                    "Review the generated configuration",
                    "Provide encryption keys (public_key_path, private_key_path)",
                    "Set encryption_template parameter for future executions",
                    "Re-run UAT with generate_encrypted_curls=true"
                ]
            }
        }

    def _format_config_for_download(self, state: BankUATState, ctx: Context) -> Dict[str, Any]:
        """Format the encryption configuration for user download"""
        config = state.get("final_encryption_config")

        if not config:
            return {
                "encryption_type": "none",
                "template_name": "no_encryption",
                "message": "No encryption configuration could be generated"
            }

        # Convert config to downloadable format
        config_dict = {
            "encryption_type": config.encryption_type,
            "template_name": config.template_name,
            "placement_strategy": config.placement_strategy,
            "algorithms": {
                "key_encryption": config.algorithms.key_encryption if config.algorithms else None,
                "payload_encryption": config.algorithms.payload_encryption if config.algorithms else None,
                "signature": config.algorithms.signature if config.algorithms else None
            },
            "headers": {name: header.to_dict() for name, header in config.headers.items()} if config.headers else {},
            "key_requirements": {
                "public_key_required": bool(config.crypto_keys.bank_public_cert_path if config.crypto_keys else False),
                "private_key_required": bool(
                    config.crypto_keys.partner_private_key_path if config.crypto_keys else False),
                "aes_key_generation": "per_transaction"
            },
            "usage_instructions": {
                "template_parameter": config.template_name,
                "required_keys": ["bank_public_cert_path",
                                  "private_key_path"] if config.template_name != "no_encryption" else [],
                "encryption_flag": "set generate_encrypted_curls=true"
            }
        }

        # Add AI analysis metadata if available
        if state.get("ai_extracted_config"):
            config_dict["ai_metadata"] = {
                "confidence_score": state["ai_extracted_config"].confidence_score,
                "detected_patterns": state["ai_extracted_config"].detected_patterns,
                "analysis_timestamp": str(ctx.task.created_at) if hasattr(ctx, 'task') else None
            }

        return config_dict

    def _format_ai_analysis_results(self, state: BankUATState) -> Dict[str, Any]:
        """Format AI analysis results for the final response"""
        ai_results = {
            "enabled": state["enable_ai_analysis"],
            "encryption_required": state["generate_encrypted_curls"],
            "analysis_performed": False,
            "validation_performed": False,
            "workflow_status": state["workflow_status"]
        }

        # Include AI analysis results if available
        if state.get("ai_extracted_config"):
            ai_results.update({
                "analysis_performed": True,
                "confidence_score": state["ai_extracted_config"].confidence_score,
                "detected_patterns": state["ai_extracted_config"].detected_patterns,
                "recommendations": state["ai_extracted_config"].recommendations,
                "extraction_metadata": state["ai_extracted_config"].extraction_metadata,
                "meets_threshold": state["ai_extracted_config"].confidence_score >= state["ai_confidence_threshold"],
                "final_configuration": {
                    "encryption_type": state["final_encryption_config"].encryption_type if state.get(
                        "final_encryption_config") else None,
                    "template_name": state["final_encryption_config"].template_name if state.get(
                        "final_encryption_config") else None,
                    "placement_strategy": state["final_encryption_config"].placement_strategy if state.get(
                        "final_encryption_config") else None,
                    "ai_detected": True
                }
            })

        # Include validation results if available
        if state.get("ai_validation_report"):
            ai_results.update({
                "validation_performed": True,
                "validation_report": state["ai_validation_report"]
            })

        # Include template recommendations if available
        if state.get("template_recommendations"):
            ai_results["template_recommendations"] = state["template_recommendations"]

        # Add status-specific information
        if state["workflow_status"] == "ai_analysis_skipped":
            ai_results["skip_reason"] = "Encryption not enabled or AI analysis disabled"
        elif state["workflow_status"] == "ai_analysis_failed":
            ai_results["failure_reason"] = state.get("error_message", "AI analysis failed")
            ai_results["fallback_used"] = True
        elif state["workflow_status"] in ["validation_skipped", "validation_failed"]:
            ai_results["validation_issue"] = state.get("error_message", "Validation was skipped or failed")

        return ai_results

    def get_ui_field_specification(self) -> Dict[str, Any]:
        """Get UI field specification for the three certificate upload fields"""
        return {
            "certificate_fields": [
                {
                    "field_name": "bank_public_cert_path",
                    "ui_label": "Bank Public Certificate",
                    "description": "Bank's public certificate for encrypting requests TO the bank",
                    "file_types": [".pem", ".crt", ".cer"],
                    "example_filenames": ["rbl_cert.pem", "bank_cert.pem", "yes_bank_cert.pem"],
                    "required": True,
                    "purpose": "encrypt_requests_to_bank",
                    "usage": "Encrypt AES keys and request payloads sent to the bank"
                },
                {
                    "field_name": "private_key_path", 
                    "ui_label": "Partner Private Key",
                    "description": "Partner's private key for decrypting responses FROM the bank",
                    "file_types": [".pem", ".key"],
                    "example_filenames": ["service_private_key.pem", "partner_private.key"],
                    "required": True,
                    "purpose": "decrypt_responses_from_bank",
                    "usage": "Decrypt response data that bank encrypted with partner's public key"
                },
                {
                    "field_name": "partner_public_key_path",
                    "ui_label": "Partner Public Key", 
                    "description": "Partner's public key for bank to encrypt responses TO partner",
                    "file_types": [".pem", ".key"],
                    "example_filenames": ["service_public_key.pem", "partner_public.key"],
                    "required": False,
                    "purpose": "bank_encrypts_responses_to_partner",
                    "usage": "Provide to bank so they can encrypt responses back to you"
                }
            ],
            "encryption_flow": {
                "request_flow": "Client → Bank: Use bank_public_cert_path to encrypt → Bank decrypts with their private key",
                "response_flow": "Bank → Client: Bank uses partner_public_key_path to encrypt → Client decrypts with private_key_path"
            },
            "ui_mapping_notes": [
                "Upload bank's certificate file to bank_public_cert_path field",
                "Upload your organization's private key to private_key_path field", 
                "Upload your organization's public key to partner_public_key_path field",
                "Do NOT use service_public_key for bank_public_cert_path - they are different!"
            ]
        }

    def get_downloadable_files(self, task_id: str) -> Dict[str, Dict[str, str]]:
        """
        Get available downloadable files for a task.
        
        Args:
            task_id: Task identifier
            
        Returns:
            Dict mapping file_type to file info dict with 'path' and 'filename'
        """
        from pathlib import Path
        
        downloadable_files = {}
        
        # Common output directories to check
        base_paths = [
            Path("uploads/bank_uat_agent/outputs"),
            Path("tmp/bank_uat_agent") / task_id,
            Path("outputs/bank_uat_agent"),
        ]
        
        # File types and their patterns
        file_types = {
            "uat_results": f"uat_results_{task_id}.txt",
            "curl_commands": f"curl_commands_{task_id}.txt",
            "test_report": f"test_report_{task_id}.txt",
            "encrypted_payloads": f"encrypted_payloads_{task_id}.txt",
            "encryption_config": f"encryption_config_{task_id}.json"
        }
        
        for file_type, filename in file_types.items():
            for base_path in base_paths:
                file_path = base_path / filename
                if file_path.exists():
                    downloadable_files[file_type] = {
                        "path": str(file_path),
                        "filename": filename
                    }
                    break
        
        return downloadable_files
    
    def get_supported_file_types(self) -> List[str]:
        """Get list of supported file types for downloads."""
        return [
            "uat_results",
            "curl_commands", 
            "test_report",
            "encrypted_payloads",
            "encryption_config"
        ]


# Register the service using the global registry instance
from ..registry import service_registry

service_registry.register("bank-uat-agent", BankUATService)
