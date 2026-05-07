"""
UAT Executor for Bank UAT Agent

This module handles comprehensive UAT execution with multi-crypto support,
parallel processing, and advanced response analysis.
"""

import asyncio
import base64
import json
import re
import secrets
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

from src.providers.context import Context
from src.providers.logger import Logger

from .rsa_crypto_manager import RSACryptoManager
from .aes_crypto_manager import AESCryptoManager
from .response_analyzer import ResponseAnalyzer


class UATExecutor:
    """
    Advanced UAT execution engine for comprehensive bank API testing
    
    Features:
    - Sequential curl execution for reliable testing
    - Multi-crypto response decryption (RSA, AES, Hybrid)
    - Comprehensive error handling and retry logic
    - Performance metrics and timing analysis
    - Response validation and analysis
    """
    
    def __init__(self, logger: Optional[Logger] = None):
        """Initialize UAT executor with optional logger"""
        self.logger = logger or Logger()
        
        # Initialize crypto managers
        self.rsa_crypto = RSACryptoManager(self.logger)
        self.aes_crypto = AESCryptoManager(self.logger)
        self.response_analyzer = ResponseAnalyzer(self.logger)
        
        # Execution configuration
        self.default_timeout = 60
        self.retry_attempts = 2
        self.retry_delay = 1.0
        self.max_concurrent_requests = 5
    
    def execute_uat_tests(
        self,
        curl_commands: List[str],
        bank_name: str,
        encryption_type: str = "aes",
        bank_public_cert_pem: Optional[str] = None,
        private_key_pem: Optional[str] = None,
        partner_public_key_pem: Optional[str] = None,
        aes_key: Optional[str] = None,
        timeout_seconds: int = 60,
        include_response_analysis: bool = True,
        custom_headers: Optional[Dict[str, str]] = None,
        generate_encrypted_curls: bool = False,
        final_encryption_config: Optional[Any] = None,  # Add EncryptionConfig parameter
        ctx: Optional[Context] = None,
        # Legacy parameter support
        public_key_pem: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Execute comprehensive UAT tests with multi-crypto support
        
        Args:
            curl_commands: List of curl commands to execute
            bank_name: Bank name for context
            encryption_type: Type of encryption (rsa, aes, hybrid, none)
            bank_public_cert_pem: Bank's public certificate (for encrypting requests TO the bank)
            private_key_pem: Partner's private key (for decrypting responses FROM the bank)
            partner_public_key_pem: Partner's public key (for bank to encrypt responses TO partner)
            aes_key: AES key for symmetric encryption (hex format)
            timeout_seconds: Request timeout
            include_response_analysis: Enable detailed response analysis
            custom_headers: Additional headers
            generate_encrypted_curls: Whether encryption is enabled for requests/responses
            final_encryption_config: Complete EncryptionConfig object from templates (preferred)
            ctx: Context for logging
            public_key_pem: Legacy parameter - use bank_public_cert_pem instead
            
        Returns:
            Comprehensive test results dictionary
        """
        self.logger.info(f"Starting UAT execution for {bank_name}: {len(curl_commands)} commands")
        
        start_time = time.time()
        
        # Setup encryption configuration - use template config if provided
        crypto_config = self._setup_encryption_config(
            encryption_type=encryption_type,
            bank_public_cert_pem=bank_public_cert_pem, 
            private_key_pem=private_key_pem, 
            partner_public_key_pem=partner_public_key_pem,
            aes_key=aes_key,
            generate_encrypted_curls=generate_encrypted_curls,
            final_encryption_config=final_encryption_config,  # Pass template config
            public_key_pem=public_key_pem  # Legacy parameter support
        )
        
        # Execute tests sequentially
        test_results = self._execute_curl_commands_sequential(
            curl_commands=curl_commands,
            bank_name=bank_name,
            crypto_config=crypto_config,
            timeout_seconds=timeout_seconds,
            include_response_analysis=include_response_analysis,
            ctx=ctx
        )
        
        # Generate comprehensive results
        execution_time = time.time() - start_time
        
        results = {
            "execution_summary": {
                "bank_name": bank_name,
                "encryption_type": encryption_type,
                "total_commands": len(curl_commands),
                "execution_time_seconds": round(execution_time, 2),
                "timestamp": datetime.now().isoformat()
            },
            "crypto_validation": crypto_config.get("validation", {}),
            "test_results": test_results,
            "performance_metrics": self._calculate_performance_metrics(test_results),
            "formatted_output": self._format_uat_output(test_results, bank_name, encryption_type, generate_encrypted_curls)
        }
        
        self.logger.info(f"UAT execution completed in {execution_time:.2f}s")
        return results
    
    def _setup_encryption_config(
        self, 
        encryption_type: str, 
        bank_public_cert_pem: Optional[str] = None, 
        private_key_pem: Optional[str] = None,
        partner_public_key_pem: Optional[str] = None,
        aes_key: Optional[str] = None,
        generate_encrypted_curls: bool = False,
        final_encryption_config: Optional[Any] = None,
        # Legacy parameter support for backward compatibility with tests
        public_key_pem: Optional[str] = None
    ) -> Dict[str, Any]:
        """Setup and validate encryption configuration using templates when available"""
        self.logger.info(f"Setting up encryption configuration for {encryption_type}")
        
        # Handle legacy parameter for backward compatibility with tests
        if public_key_pem is not None and bank_public_cert_pem is None:
            bank_public_cert_pem = public_key_pem
        
        # Import required classes
        try:
            from .crypto.configurable_crypto_manager import ConfigurableCryptoManager
            from .config.encryption_config import EncryptionConfig, EncryptionType
        except ImportError as e:
            self.logger.warning(f"Could not import configurable crypto components: {e}")
            # Fallback to legacy configuration
            return self._setup_legacy_encryption_config(
                encryption_type, bank_public_cert_pem, private_key_pem, 
                partner_public_key_pem, aes_key, generate_encrypted_curls
            )
        
        # Initialize configurable crypto manager
        configurable_crypto = ConfigurableCryptoManager(self.logger)
        
        # Use template configuration if provided
        if final_encryption_config:
            try:
                self.logger.info("Using template-based encryption configuration")
                self.logger.info(f"  Template: {getattr(final_encryption_config, 'template_name', 'Custom')}")
                self.logger.info(f"  Encryption type: {getattr(final_encryption_config, 'encryption_type', 'Unknown')}")
                self.logger.info(f"  Placement strategy: {getattr(final_encryption_config, 'placement_strategy', 'Unknown')}")
                
                # Generate AES key if not provided (before parallel execution)
                if not aes_key and encryption_type in ["hybrid", "auto_detect"]:
                    import secrets
                    aes_key = secrets.token_hex(32)  # 256-bit key
                    self.logger.info("Generated AES key for template-based encryption (shared across all curls)")
                
                # Create enhanced configuration from template
                config = {
                    "type": encryption_type,
                    "generate_encrypted_curls": generate_encrypted_curls,
                    "encryption_config": final_encryption_config,  # Store the full template config
                    "configurable_crypto": configurable_crypto,
                    "use_template": True,
                    
                    # Key materials
                    "public_key": bank_public_cert_pem,
                    "private_key": private_key_pem,
                    "partner_public_key": partner_public_key_pem,
                    "aes_key": aes_key,
                    
                    # Template-specific configuration
                    "placement_strategy": getattr(final_encryption_config, 'placement_strategy', 'headers'),
                    "algorithms": getattr(final_encryption_config, 'algorithms', None),
                    "headers_config": getattr(final_encryption_config, 'headers', {}),
                    "body_structure": getattr(final_encryption_config, 'body_structure', {}),
                    
                    # Extract padding configuration
                    "rsa_padding": "PKCS1",  # Default
                    "aes_padding": "PKCS7",  # Default
                    
                    "validation": {
                        "crypto_available": True,
                        "keys_validated": True,
                        "setup_successful": True,
                        "template_applied": True,
                        "template_name": getattr(final_encryption_config, 'template_name', 'Custom')
                    }
                }
                
                # Extract padding from algorithms if available
                if hasattr(final_encryption_config, 'algorithms') and final_encryption_config.algorithms:
                    algorithms = final_encryption_config.algorithms
                    if hasattr(algorithms, 'padding') and algorithms.padding:
                        padding_config = algorithms.padding
                        if hasattr(padding_config, 'rsa_padding'):
                            config["rsa_padding"] = padding_config.rsa_padding
                        if hasattr(padding_config, 'aes_padding'):
                            config["aes_padding"] = padding_config.aes_padding
                
                self.logger.info("Template-based encryption configuration created successfully")
                return config
                
            except Exception as e:
                self.logger.error(f"Failed to use template configuration: {e}")
                self.logger.info("Falling back to legacy configuration")
                # Continue to legacy setup below
        
        # Fallback to legacy configuration if no template or template failed
        return self._setup_legacy_encryption_config(
            encryption_type, bank_public_cert_pem, private_key_pem, 
            partner_public_key_pem, aes_key, generate_encrypted_curls
        )
    
    def _setup_legacy_encryption_config(
        self,
        encryption_type: str, 
        bank_public_cert_pem: Optional[str], 
        private_key_pem: Optional[str],
        partner_public_key_pem: Optional[str] = None,
        aes_key: Optional[str] = None,
        generate_encrypted_curls: bool = False
    ) -> Dict[str, Any]:
        """Legacy encryption configuration setup (backward compatibility)"""
        self.logger.info("Using legacy encryption configuration")
        
        config = {
            "type": encryption_type,
            "generate_encrypted_curls": generate_encrypted_curls,
            "use_template": False,
            "aes_key": aes_key,
            "validation": {
                "crypto_available": False,
                "keys_validated": False,
                "setup_successful": False,
                "template_applied": False
            }
        }
        
        # Add key materials to config
        if bank_public_cert_pem:
            config["public_key"] = bank_public_cert_pem
            config["validation"]["crypto_available"] = True
            
        if private_key_pem:
            config["private_key"] = private_key_pem
            config["validation"]["keys_validated"] = True
            
        if partner_public_key_pem:
            config["partner_public_key"] = partner_public_key_pem
        
        # Set default padding for legacy compatibility
        config["rsa_padding"] = "PKCS1"
        config["aes_padding"] = "PKCS7"
        
        # Basic validation
        if encryption_type == "none":
            config["validation"]["crypto_available"] = True
            config["validation"]["keys_validated"] = True
            config["validation"]["setup_successful"] = True
        elif encryption_type == "aes":
            # AES encryption is always considered available (uses default key if none provided)
            config["validation"]["crypto_available"] = True
            config["validation"]["keys_validated"] = True
            config["validation"]["setup_successful"] = True
        elif encryption_type == "signature_only":
            # Signature-only mode needs private key for validation
            config["validation"]["crypto_available"] = True
            if private_key_pem:
                config["validation"]["keys_validated"] = True
                config["validation"]["setup_successful"] = True
            else:
                config["validation"]["keys_validated"] = False
                config["validation"]["setup_successful"] = False
        elif generate_encrypted_curls and encryption_type in ["rsa", "hybrid", "auto_detect"]:
            # RSA-based encryption needs public key for request encryption
            if not bank_public_cert_pem:
                self.logger.warning(f"{encryption_type} encryption requested but no bank public certificate provided")
                config["validation"]["setup_successful"] = False
                if encryption_type == "rsa":
                    config["validation"]["error"] = "RSA public key required for encryption"
            else:
                config["validation"]["crypto_available"] = True
                config["validation"]["setup_successful"] = True
        else:
            # No encryption curls but validation should still pass
            config["validation"]["crypto_available"] = True
            config["validation"]["keys_validated"] = True  
            config["validation"]["setup_successful"] = True
        
        self.logger.info(f"Legacy encryption configuration setup complete: {config['validation']}")
        return config
    

    def _execute_curl_commands_sequential(
        self,
        curl_commands: List[str],
        bank_name: str,
        crypto_config: Dict[str, Any],
        timeout_seconds: int,
        include_response_analysis: bool,
        ctx: Optional[Context]
    ) -> List[Dict[str, Any]]:
        """Execute curl commands sequentially one by one"""
        results = []
        
        self.logger.info(f"Executing {len(curl_commands)} curl commands sequentially")
        
        for i, curl_cmd in enumerate(curl_commands):
            test_number = i + 1
            self.logger.info(f"Processing curl command {test_number} of {len(curl_commands)}")
            
            try:
                result = self._execute_single_curl(
                    curl_cmd, test_number, bank_name, crypto_config, 
                    timeout_seconds, include_response_analysis, ctx
                )
                results.append(result)
                
                # Log progress
                self.logger.info(f"Completed curl {test_number}: {result.get('status', 'unknown')} in {result.get('execution_time', 0)}s")
                
            except Exception as e:
                self.logger.error(f"Curl execution failed for command {test_number}: {str(e)}")
                error_result = {
                    "test_number": test_number,
                    "curl_command": curl_cmd,
                    "status": "failed",
                    "error": str(e),
                    "execution_time": 0,
                    "response_data": None
                }
                results.append(error_result)
        
        self.logger.info(f"Sequential execution completed: {len(results)} results")
        return results
    
    def _execute_single_curl(
        self,
        curl_command: str,
        test_number: int,
        bank_name: str,
        crypto_config: Dict[str, Any],
        timeout_seconds: int,
        include_response_analysis: bool,
        ctx: Optional[Context]
    ) -> Dict[str, Any]:
        """Execute a single curl command with comprehensive analysis"""
        start_time = time.time()
        
        self.logger.info(f"Executing test {test_number}: {curl_command}")
        
        result = {
            "test_number": test_number,
            "curl_command": curl_command,
            "modified_curl_command": None,
            "status": "unknown",
            "execution_time": 0,
            "response_data": None,
            "decrypted_response": None,
            "analysis": None,
            "error": None,
            "encryption_applied": False
        }
        
        try:
            # Determine which curl command to execute
            curl_to_execute = curl_command
            
            # Apply request encryption if needed
            if crypto_config.get("generate_encrypted_curls", False) and crypto_config.get("type", "none") != "none":
                self.logger.info(f"Applying {crypto_config['type']} encryption to request")
                
                # Parse the original cURL command
                self.logger.debug(f"Original curl command: {curl_command}")
                parsed_curl = self._parse_curl_command(curl_command)
                self.logger.debug(f"Parsed curl result: {parsed_curl}")
                
                # Apply encryption regardless of payload presence for consistency
                payload = parsed_curl.get("payload")
                if payload:
                    self.logger.info(f"Found payload for encryption: {type(payload)} - {str(payload)[:100]}...")
                else:
                    self.logger.info("No payload found - applying encryption headers only for consistency")
                
                # Encrypt the payload (or apply headers even if no payload)
                self.logger.raw_info(f"🔐 ENCRYPTION DEBUG - Original payload: {payload}")
                encrypted_payload, extra_headers = self._encrypt_request_payload(
                    payload, 
                    crypto_config["type"],
                    crypto_config
                )
                self.logger.raw_info(f"🔐 ENCRYPTION DEBUG - Encrypted payload: {encrypted_payload}")
                self.logger.raw_info(f"🔐 ENCRYPTION DEBUG - Extra headers: {extra_headers}")
                
                # Reconstruct cURL with encrypted payload and headers
                self.logger.raw_info(f"🔧 RECONSTRUCTION DEBUG - Before reconstruction:")
                self.logger.raw_info(f"  Original parsed curl: {parsed_curl}")
                
                curl_to_execute = self._reconstruct_curl_command(
                    parsed_curl, 
                    new_payload=encrypted_payload if payload else None,
                    additional_headers=extra_headers
                )
                
                self.logger.raw_info(f"🔧 RECONSTRUCTION DEBUG - After reconstruction:")
                self.logger.raw_info(f"  New curl command: {curl_to_execute}")
                
                result["modified_curl_command"] = curl_to_execute
                result["encryption_applied"] = True
                
                self.logger.info(f"Request encrypted using {crypto_config['type']}")
                self.logger.raw_info(f"FINAL ENCRYPTED CURL: {curl_to_execute}")
            else:
                self.logger.info("Encryption not requested or type is 'none' - executing original curl")
            
            # Execute curl with retries
            response_data = self._execute_curl_with_retry(curl_to_execute, timeout_seconds)
            
            result["status"] = "success"
            result["response_data"] = response_data
            
            self.logger.raw_info(f"Encrypted Response data: {response_data}")
            # Attempt response decryption
            if crypto_config.get("validation", {}).get("crypto_available", False):
                decrypted_response = self._decrypt_response(response_data, crypto_config)
                result["decrypted_response"] = decrypted_response
            
            # Perform response analysis if enabled
            if include_response_analysis:
                analysis = self.response_analyzer.analyze_response(
                    response_data, 
                    result.get("decrypted_response"),
                    bank_name
                )
                result["analysis"] = analysis
            
        except subprocess.TimeoutExpired:
            result["status"] = "timeout"
            result["error"] = f"Request timed out after {timeout_seconds} seconds"
            
        except subprocess.CalledProcessError as e:
            result["status"] = "error"
            result["error"] = f"Curl failed with exit code {e.returncode}: {e.stderr}"
            
        except Exception as e:
            result["status"] = "failed"
            result["error"] = str(e)
        
        result["execution_time"] = round(time.time() - start_time, 2)
        
        self.logger.info(f"Test {test_number} completed: {result['status']} in {result['execution_time']}s")
        return result
    
    def _execute_curl_with_retry(self, curl_command: str, timeout_seconds: int) -> str:
        """Execute curl command with retry logic"""
        last_exception = None
        
        for attempt in range(self.retry_attempts + 1):
            try:
                # Clean and prepare curl command
                cleaned_curl = self._clean_curl_command(curl_command)
                
                # Execute curl
                result = subprocess.run(
                    cleaned_curl,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=timeout_seconds,
                    check=False  # Don't raise on non-zero exit codes
                )
                
                # Only use stdout for response data, log stderr separately if needed
                response = result.stdout
                if result.stderr:
                    # Log stderr separately without including it in response
                    self.logger.debug(f"cURL stderr output: {result.stderr}")
                
                # Check if we got a reasonable response
                if result.returncode == 0 or len(response.strip()) > 0:
                    return response
                
                # If empty response and non-zero exit code, treat as error
                if result.returncode != 0:
                    raise subprocess.CalledProcessError(result.returncode, cleaned_curl, result.stdout, result.stderr)
                
            except (subprocess.TimeoutExpired, subprocess.CalledProcessError) as e:
                last_exception = e
                if attempt < self.retry_attempts:
                    self.logger.warning(f"Curl attempt {attempt + 1} failed, retrying in {self.retry_delay}s: {str(e)}")
                    time.sleep(self.retry_delay)
                else:
                    raise
        
        # This should not be reached, but just in case
        if last_exception:
            raise last_exception
        else:
            raise Exception("Curl execution failed for unknown reason")
    
    def _clean_curl_command(self, curl_command: str) -> str:
        """Clean and prepare curl command for execution"""
        # Remove line continuations and extra whitespace
        cleaned = curl_command.replace('\\\n', ' ').replace('\\', '')
        cleaned = ' '.join(cleaned.split())  # Normalize whitespace
        
        # Ensure curl is at the beginning
        if not cleaned.strip().startswith('curl'):
            cleaned = 'curl ' + cleaned.strip()
        
        return cleaned
    
    def _parse_curl_command(self, curl_command: str) -> Dict[str, Any]:
        """
        Parse cURL command to extract components for encryption
        
        Returns:
            Dict containing url, method, headers, payload, and other options
        """
        try:
            # Clean the command first
            cleaned_curl = self._clean_curl_command(curl_command)
            self.logger.debug(f"Cleaned curl command: {cleaned_curl}")
            
            # Initialize result
            parsed = {
                "url": None,
                "method": "GET",
                "headers": {},
                "payload": None,
                "raw_payload": None,
                "other_options": []
            }
            
            # Extract URL (look for http/https URLs)
            url_match = re.search(r'https?://[^\s"\']+', cleaned_curl)
            if url_match:
                parsed["url"] = url_match.group(0).strip('"\'')
                self.logger.debug(f"Extracted URL: {parsed['url']}")
            
            # Extract method (-X or --request)
            method_match = re.search(r'-X\s+(\w+)|--request\s+(\w+)', cleaned_curl)
            if method_match:
                parsed["method"] = (method_match.group(1) or method_match.group(2)).upper()
                self.logger.debug(f"Extracted method: {parsed['method']}")
            
            # Extract headers (-H or --header)
            header_matches = re.findall(r'-H\s+["\']([^"\']+)["\']|--header\s+["\']([^"\']+)["\']', cleaned_curl)
            for header_tuple in header_matches:
                header = header_tuple[0] or header_tuple[1]
                if ':' in header:
                    key, value = header.split(':', 1)
                    parsed["headers"][key.strip()] = value.strip()
            self.logger.debug(f"Extracted {len(parsed['headers'])} headers: {list(parsed['headers'].keys())}")
            
            # Extract payload data (-d, --data, --data-raw) - handle quotes properly
            data_patterns = [
                r"-d\s+'([^']+)'",  # Single quotes
                r'-d\s+"([^"]+)"',  # Double quotes
                r"--data\s+'([^']+)'",
                r'--data\s+"([^"]+)"',
                r"--data-raw\s+'([^']+)'",
                r'--data-raw\s+"([^"]+)"'
            ]
            
            payload_found = False
            for i, pattern in enumerate(data_patterns, 1):
                data_match = re.search(pattern, cleaned_curl)
                if data_match:
                    parsed["raw_payload"] = data_match.group(1)
                    self.logger.debug(f"Found payload with pattern {i}: {parsed['raw_payload']}")
                    
                    # Try to parse as JSON
                    try:
                        parsed["payload"] = json.loads(parsed["raw_payload"])
                        self.logger.debug(f"Successfully parsed payload as JSON: {type(parsed['payload'])}")
                    except json.JSONDecodeError as e:
                        # If not JSON, keep as string
                        parsed["payload"] = parsed["raw_payload"]
                        self.logger.debug(f"Payload not valid JSON, keeping as string: {e}")
                    
                    payload_found = True
                    break
            
            if not payload_found:
                self.logger.debug("No payload found with any pattern")
                # Check if there's a -d flag at all
                if ' -d ' in cleaned_curl:
                    self.logger.debug("Found -d flag but couldn't extract payload - possible quote issue")
                    # Try a more liberal extraction
                    parts = cleaned_curl.split(' -d ', 1)
                    if len(parts) > 1:
                        data_part = parts[1].split(' -')[0].strip()
                        self.logger.debug(f"Raw data part after -d: {data_part}")
            
            return parsed
            
        except Exception as e:
            self.logger.warning(f"Failed to parse cURL command: {str(e)}")
            self.logger.debug(f"Problematic curl command: {curl_command}")
            return {
                "url": None,
                "method": "GET", 
                "headers": {},
                "payload": None,
                "raw_payload": None,
                "other_options": []
            }
    
    def _encrypt_request_payload(self, payload: Any, encryption_type: str, crypto_config: Dict[str, Any]) -> Tuple[str, Dict[str, str]]:
        """
        Encrypt request payload based on encryption type and template configuration
        
        Returns:
            Tuple of (encrypted_payload_string, additional_headers_dict)
        """
        if encryption_type == "none":
            return json.dumps(payload) if payload else "", {}
        
        try:
            # Convert payload to JSON string if it's a dict, or use empty string if no payload
            if payload:
                if isinstance(payload, dict):
                    payload_str = json.dumps(payload)
                else:
                    payload_str = str(payload)
            else:
                payload_str = ""  # Empty payload for GET requests
            
            additional_headers = {}
            
            # Check if using template-based encryption
            if crypto_config.get("use_template", False) and crypto_config.get("encryption_config"):
                return self._encrypt_with_template(payload_str, crypto_config, additional_headers)
            
            # Fallback to hybrid encryption for auto_detect
            if encryption_type in ["hybrid", "auto_detect"]:
                return self._encrypt_hybrid_payload(payload_str, crypto_config, additional_headers)
            
            else:
                self.logger.warning(f"Unknown encryption type: {encryption_type}")
                return payload_str, {}
                
        except Exception as e:
            self.logger.error(f"Failed to encrypt payload: {str(e)}")
            return json.dumps(payload) if isinstance(payload, dict) else str(payload), {}
    
    def _encrypt_with_template(self, payload_str: str, crypto_config: Dict[str, Any], headers: Dict[str, str]) -> Tuple[str, Dict[str, str]]:
        """Encrypt payload using template-based configuration"""
        try:
            encryption_config = crypto_config["encryption_config"]
            configurable_crypto = crypto_config["configurable_crypto"]
            
            self.logger.info("Encrypting payload using template configuration")
            self.logger.info(f"  Template: {getattr(encryption_config, 'template_name', 'Custom')}")
            self.logger.info(f"  Placement strategy: {crypto_config.get('placement_strategy', 'headers')}")
            
            # Get placement strategy
            placement_strategy = crypto_config.get("placement_strategy", "headers")
            self.logger.raw_info(f"🎯 STRATEGY SELECTION - Selected strategy: {placement_strategy}")
            
            if placement_strategy == "headers":
                self.logger.raw_info(f"🎯 STRATEGY SELECTION - Calling _encrypt_with_header_strategy")
                return self._encrypt_with_header_strategy(payload_str, crypto_config, headers)
            elif placement_strategy == "body":
                self.logger.raw_info(f"🎯 STRATEGY SELECTION - Calling _encrypt_with_body_strategy")
                return self._encrypt_with_body_strategy(payload_str, crypto_config, headers)
            elif placement_strategy == "mixed":
                self.logger.raw_info(f"🎯 STRATEGY SELECTION - Calling _encrypt_with_mixed_strategy")
                return self._encrypt_with_mixed_strategy(payload_str, crypto_config, headers)
            else:
                self.logger.warning(f"Unknown placement strategy: {placement_strategy}, falling back to headers")
                self.logger.raw_info(f"🎯 STRATEGY SELECTION - Fallback to _encrypt_with_header_strategy")
                return self._encrypt_with_header_strategy(payload_str, crypto_config, headers)
                
        except Exception as e:
            self.logger.error(f"Template-based encryption failed: {e}")
            # Fail consistently instead of falling back to different encryption type
            raise Exception(f"Template-based encryption failed for configured template: {e}")
    
    def _encrypt_with_header_strategy(self, payload_str: str, crypto_config: Dict[str, Any], headers: Dict[str, str]) -> Tuple[str, Dict[str, str]]:
        """Encrypt using header-based placement strategy (like RBL pattern)"""
        try:
            self.logger.info("Using header-based encryption strategy")
            
            # Get key materials
            public_key = crypto_config.get("public_key")  # Bank's public certificate
            private_key = crypto_config.get("private_key")  # Partner's private key for signing
            aes_key = crypto_config.get("aes_key")
            
            # Get header configuration from template
            headers_config = crypto_config.get("headers_config", {})
            
            if not public_key:
                raise ValueError("Bank public certificate required for header-based encryption")
            
            # AES key should have been generated during config setup for thread safety
            if not aes_key:
                self.logger.error("AES key not available for header-based encryption - should have been generated during config setup")
                raise ValueError("AES key missing for header-based encryption")
            
            # 1. Encrypt payload with AES (only if payload exists)
            if payload_str:
                aes_encrypted_payload = self.aes_crypto.encrypt_payload(payload_str, aes_key)
                self.logger.raw_info(f"🔐 AES ENCRYPTION - Original payload: {payload_str}")
                self.logger.raw_info(f"🔐 AES ENCRYPTION - AES key (hex): {aes_key}")
                self.logger.raw_info(f"🔐 AES ENCRYPTION - Encrypted payload: {aes_encrypted_payload}")
            else:
                aes_encrypted_payload = ""
                self.logger.info("🔐 AES ENCRYPTION - No payload to encrypt, generating headers only")
            
            # 2. Encrypt AES key with bank's public certificate
            from cryptography.hazmat.primitives import serialization
            public_key_obj = serialization.load_pem_public_key(
                public_key.encode('utf-8')
            )
            
            # Use configurable padding
            rsa_padding = crypto_config.get("rsa_padding", "PKCS1")
            aes_key_bytes = aes_key.encode('utf-8') if isinstance(aes_key, str) else aes_key
            encrypted_aes_key_bytes = self.rsa_crypto.encrypt_with_padding(
                aes_key_bytes,
                public_key_obj,
                rsa_padding
            )
            rsa_encrypted_key = base64.b64encode(encrypted_aes_key_bytes).decode('utf-8')
            self.logger.raw_info(f"🔐 RSA ENCRYPTION - AES key bytes: {len(aes_key_bytes)} bytes")
            self.logger.raw_info(f"🔐 RSA ENCRYPTION - Encrypted AES key (b64): {rsa_encrypted_key}")
            
            # 3. Generate signature if private key available
            signature_b64 = None
            if private_key:
                try:
                    private_key_obj = serialization.load_pem_private_key(
                        private_key.encode('utf-8'),
                        password=None
                    )
                    
                    # Sign the payload if it exists, otherwise sign empty string for consistency
                    sign_data = payload_str.encode('utf-8') if payload_str else b""
                    signature = self.rsa_crypto.sign_with_padding(
                        sign_data,
                        private_key_obj,
                        rsa_padding,
                        "SHA256"
                    )
                    signature_b64 = base64.b64encode(signature).decode('utf-8')
                    self.logger.info(f"Payload signed successfully ({'with payload' if payload_str else 'empty payload'})")
                    self.logger.raw_info(f"🔐 SIGNATURE - Signature (b64): {signature_b64}")
                except Exception as e:
                    self.logger.warning(f"Could not sign payload: {e}")
            
            # 4. Partner ID encryption removed - not needed since partner header was removed
            
            # 5. Generate IV (16-digit numeric for RBL compatibility)
            iv_numeric = ''.join([str(secrets.randbelow(10)) for _ in range(16)])
            self.logger.raw_info(f"🔐 IV - Generated IV: {iv_numeric}")
            
            # 6. Build headers based on template configuration
            template_headers = {}
            
            # Map template header config to actual headers
            for header_key, header_config in headers_config.items():
                if hasattr(header_config, 'name') and hasattr(header_config, 'source'):
                    header_name = header_config.name
                    header_source = header_config.source
                    
                    if header_source == "signature" and signature_b64:
                        template_headers[header_name] = signature_b64
                    elif header_source == "encrypted_aes_key":
                        template_headers[header_name] = rsa_encrypted_key
                    elif header_source == "generated_iv":
                        template_headers[header_name] = iv_numeric
                    elif header_source == "static_value" and hasattr(header_config, 'static_value'):
                        template_headers[header_name] = header_config.static_value
                    # Note: encrypted_partner_id source removed as partner header is no longer needed
            
            # Fallback to standard RBL headers if template doesn't specify
            if not template_headers:
                template_headers = {
                    "token": signature_b64 if signature_b64 else "",
                    "key": rsa_encrypted_key,
                    "iv": iv_numeric,
                    "Content-Type": "application/json"
                }
            
            headers.update(template_headers)
            
            self.logger.info("Header-based encryption completed successfully")
            self.logger.info(f"Generated headers: {list(template_headers.keys())}")
            
            return aes_encrypted_payload, headers
            
        except Exception as e:
            self.logger.error(f"Header-based encryption failed: {e}")
            raise
    
    def _encrypt_with_body_strategy(self, payload_str: str, crypto_config: Dict[str, Any], headers: Dict[str, str]) -> Tuple[str, Dict[str, str]]:
        """Encrypt using body-based placement strategy (like JSON body with encrypted_key/encrypted_data)"""
        try:
            self.logger.info("Using body-based encryption strategy")
            
            # Get key materials
            public_key = crypto_config.get("public_key")  # Bank's public certificate
            aes_key = crypto_config.get("aes_key")
            
            if not public_key:
                raise ValueError("Bank public certificate required for body-based encryption")
            
            # AES key should have been generated during config setup for thread safety
            if not aes_key:
                self.logger.error("AES key not available for body-based encryption - should have been generated during config setup")
                raise ValueError("AES key missing for body-based encryption")
            
            # 1. Encrypt payload with AES (only if payload exists)
            if payload_str:
                aes_encrypted_payload = self.aes_crypto.encrypt_payload(payload_str, aes_key)
            else:
                aes_encrypted_payload = ""  # Empty payload for GET requests
            
            # 2. Encrypt AES key with bank's public certificate
            from cryptography.hazmat.primitives import serialization
            public_key_obj = serialization.load_pem_public_key(
                public_key.encode('utf-8')
            )
            
            # Use configurable padding
            rsa_padding = crypto_config.get("rsa_padding", "PKCS1")
            aes_key_bytes = aes_key.encode('utf-8') if isinstance(aes_key, str) else aes_key
            encrypted_aes_key_bytes = self.rsa_crypto.encrypt_with_padding(
                aes_key_bytes,
                public_key_obj,
                rsa_padding
            )
            rsa_encrypted_key = base64.b64encode(encrypted_aes_key_bytes).decode('utf-8')
            
            # 3. Create body structure
            body_structure = {
                "encrypted_key": rsa_encrypted_key,
                "encrypted_data": aes_encrypted_payload
            }
            
            headers["Content-Type"] = "application/json"
            
            self.logger.info("Body-based encryption completed successfully")
            
            return json.dumps(body_structure), headers
            
        except Exception as e:
            self.logger.error(f"Body-based encryption failed: {e}")
            raise
    
    def _encrypt_with_mixed_strategy(self, payload_str: str, crypto_config: Dict[str, Any], headers: Dict[str, str]) -> Tuple[str, Dict[str, str]]:
        """Encrypt using mixed placement strategy (combination of headers and body)"""
        try:
            self.logger.info("Using mixed encryption strategy")
            
            # For now, fallback to header-based strategy
            # TODO: Implement actual mixed strategy based on template configuration
            self.logger.warning("Mixed strategy not fully implemented, using header-based fallback")
            return self._encrypt_with_header_strategy(payload_str, crypto_config, headers)
            
        except Exception as e:
            self.logger.error(f"Mixed encryption failed: {e}")
            raise
    


    def _encrypt_hybrid_payload(self, payload_str: str, crypto_config: Dict[str, Any], headers: Dict[str, str]) -> Tuple[str, Dict[str, str]]:
        """Encrypt payload using RSA+AES hybrid approach"""
        public_key = crypto_config.get("public_key")  # Bank's public certificate
        aes_key = crypto_config.get("aes_key")
        rsa_padding = crypto_config.get("rsa_padding", "PKCS1")  # Get configurable padding
        
        if not public_key:
            self.logger.error("No RSA public key available for hybrid encryption")
            return payload_str, headers
        
        try:
            # AES key should have been generated during config setup for thread safety
            if not aes_key:
                import secrets
                aes_key = secrets.token_hex(32)  # 256-bit key
                self.logger.warning("Generating AES key in hybrid method - should have been done during config setup")
            
            # 1. Encrypt payload with AES (only if payload exists)
            if payload_str:
                aes_encrypted_payload = self.aes_crypto.encrypt_payload(payload_str, aes_key)
            else:
                aes_encrypted_payload = ""  # Empty payload for GET requests
            
            # 2. Encrypt AES key with bank's public certificate using configurable padding
            # Load the public key as crypto object for padding-aware encryption
            from cryptography.hazmat.primitives import serialization
            public_key_obj = serialization.load_pem_public_key(
                public_key.encode('utf-8')
            )
            
            # Use configurable padding instead of hardcoded OAEP
            aes_key_bytes = aes_key.encode('utf-8') if isinstance(aes_key, str) else aes_key
            encrypted_aes_key_bytes = self.rsa_crypto.encrypt_with_padding(
                aes_key_bytes, 
                public_key_obj, 
                rsa_padding
            )
            rsa_encrypted_key = base64.b64encode(encrypted_aes_key_bytes).decode('utf-8')
            
            # 3. Create hybrid structure
            hybrid_data = {
                "encrypted_key": rsa_encrypted_key,
                "encrypted_data": aes_encrypted_payload
            }
            
            headers["Content-Type"] = "application/json"
            
            return json.dumps(hybrid_data), headers
            
        except Exception as e:
            self.logger.error(f"Hybrid encryption failed: {str(e)}")
            return payload_str, headers
    

    def _reconstruct_curl_command(self, parsed_curl: Dict[str, Any], new_payload: Optional[str] = None, additional_headers: Optional[Dict[str, str]] = None) -> str:
        """
        Rebuild cURL command with modified payload and headers
        """
        if not parsed_curl.get("url"):
            self.logger.error("Cannot reconstruct cURL - no URL found")
            return ""
        
        # Start building the command
        parts = ["curl"]
        
        # Add method
        if parsed_curl.get("method", "GET") != "GET":
            parts.extend(["-X", parsed_curl["method"]])
        
        # Add original headers
        headers = parsed_curl.get("headers", {}).copy()
        
        # Add additional headers from encryption
        if additional_headers:
            headers.update(additional_headers)
        
        # Add all headers
        for key, value in headers.items():
            parts.extend(["-H", f'"{key}: {value}"'])
        
        # Add payload if provided
        if new_payload:
            parts.extend(["-d", f"'{new_payload}'"])
        elif parsed_curl.get("raw_payload"):
            parts.extend(["-d", f"'{parsed_curl['raw_payload']}'"])
        
        # Add URL (quoted to handle special characters)
        parts.append(f'"{parsed_curl["url"]}"')
        
        return " ".join(parts)
    
    def _decrypt_response(self, response: str, crypto_config: Dict[str, Any]) -> Optional[str]:
        """Decrypt response based on encryption configuration"""
        if not response or not response.strip():
            return None
        
        # Only attempt decryption if encryption is enabled
        if not crypto_config.get("generate_encrypted_curls", False):
            return None
        
        encryption_type = crypto_config.get("type", "none")
        
        # Handle signature-only mode (no decryption needed, just return as-is)
        if encryption_type == "signature_only":
            return response.strip()
        
        try:
            if encryption_type == "aes":
                # Handle AES decryption
                if self.aes_crypto.looks_like_encrypted_response(response):
                    aes_key = crypto_config.get("aes_key") or self.aes_crypto.DEFAULT_HEX_KEY
                    return self.aes_crypto.decrypt_payload(response, aes_key)
                    
            elif encryption_type in ["hybrid", "auto_detect"]:
                private_key = crypto_config.get("private_key")  # Partner's private key
                rsa_padding = crypto_config.get("rsa_padding", "PKCS1")  # Get configurable padding
                if private_key and self._looks_like_encrypted_response(response):
                    # Try hybrid decryption with configurable padding
                    from cryptography.hazmat.primitives import serialization
                    private_key_obj = serialization.load_pem_private_key(
                        private_key.encode('utf-8'), 
                        password=None
                    )
                    
                    try:
                        # Decrypt response using partner's private key with configurable padding
                        encrypted_bytes = base64.b64decode(response.strip())
                        decrypted_bytes = self.rsa_crypto.decrypt_with_padding(
                            encrypted_bytes,
                            private_key_obj,
                            rsa_padding
                        )
                        return decrypted_bytes.decode('utf-8')
                    except:
                        # If hybrid fails, might be pure RSA - try again
                        try:
                            encrypted_bytes = base64.b64decode(response.strip())
                            decrypted_bytes = self.rsa_crypto.decrypt_with_padding(
                                encrypted_bytes,
                                private_key_obj,
                                rsa_padding
                            )
                            return decrypted_bytes.decode('utf-8')
                        except:
                            self.logger.warning("Hybrid decryption failed with configurable padding")
                            return None
            
        except Exception as e:
            self.logger.warning(f"Response decryption failed ({encryption_type}): {str(e)}")
        
        return None
    
    def _looks_like_encrypted_response(self, response: str) -> bool:
        """Check if response appears to be encrypted"""
        if not response or len(response.strip()) < 20:
            return False
        
        # Check for base64-like patterns or JSON with encrypted fields
        try:
            # Try base64 decode
            import base64
            decoded = base64.b64decode(response.strip())
            if len(decoded) >= 32:  # Minimum for encrypted data with IV
                return True
        except:
            pass
        
        # Check for JSON with encrypted fields
        try:
            data = json.loads(response.strip())
            if isinstance(data, dict):
                encrypted_fields = ['encrypted_data', 'cipher', 'payload', 'data', 'encrypted']
                return any(field in data for field in encrypted_fields)
        except:
            pass
        
        return False
    
    def _calculate_performance_metrics(self, test_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate performance metrics from test results"""
        if not test_results:
            return {}
        
        execution_times = [r.get("execution_time", 0) for r in test_results]
        successful_tests = [r for r in test_results if r.get("status") == "success"]
        failed_tests = [r for r in test_results if r.get("status") in ["failed", "error"]]
        timeout_tests = [r for r in test_results if r.get("status") == "timeout"]
        
        return {
            "total_tests": len(test_results),
            "successful_tests": len(successful_tests),
            "failed_tests": len(failed_tests),
            "timeout_tests": len(timeout_tests),
            "success_rate": round(len(successful_tests) / len(test_results) * 100, 2),
            "performance": {
                "min_execution_time": round(min(execution_times) if execution_times else 0, 2),
                "max_execution_time": round(max(execution_times) if execution_times else 0, 2),
                "avg_execution_time": round(sum(execution_times) / len(execution_times) if execution_times else 0, 2),
                "total_execution_time": round(sum(execution_times), 2)
            }
        }
    
    def _format_uat_output(
        self, 
        test_results: List[Dict[str, Any]], 
        bank_name: str, 
        encryption_type: str,
        generate_encrypted_curls: bool = False
    ) -> str:
        """Format UAT results in UAT_LangGraph compatible format"""
        
        # Header based on encryption type
        if encryption_type in ["rsa", "hybrid"]:
            header = f"=== UAT Testing Results (With RSA Encryption) ===\n\n"
        elif encryption_type == "aes":
            header = f"=== UAT Testing Results (With AES Encryption) ===\n\n"
        else:
            header = f"=== UAT Testing Results (No Encryption) ===\n\n"
        
        output = header
        output += f"Bank: {bank_name}\n"
        output += f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        
        for result in test_results:
            test_num = result.get("test_number", 0)
            curl_cmd = result.get("curl_command", "")
            encrypted_curl_cmd = result.get("modified_curl_command", "")
            status = result.get("status", "unknown")
            response_data = result.get("response_data", "")
            decrypted_response = result.get("decrypted_response")
            error = result.get("error")
            
            output += f"--- Test {test_num} ---\n"
            
            if generate_encrypted_curls and encryption_type in ["rsa", "hybrid", "aes"]:
                # Show both original and encrypted format for compatibility
                output += f"1. Original cURL Command (Non-Encrypted Request):\n{curl_cmd}\n\n"
                output += f"2. Encrypted cURL Command (Encrypted Request):\n{encrypted_curl_cmd}\n\n"
                
                if status == "success":
                    output += f"3. Encrypted Response:\n{response_data}\n\n"
                    
                    if decrypted_response and decrypted_response != response_data:
                        output += f"4. Decrypted Response (Non-Encrypted Response):\n{decrypted_response}\n"
                    else:
                        output += f"4. Decrypted Response (Non-Encrypted Response): Response doesn't appear to be encrypted or decryption failed\n"
                else:
                    output += f"3. Encrypted Response: {error or 'Request failed'}\n"
                    output += f"4. Decrypted Response (Non-Encrypted Response): N/A\n"
            else:
                # No encryption format - simple output
                output += f"cURL Command:\n{curl_cmd}\n\n"
                
                if status == "success":
                    output += f"Response:\n{response_data}\n\n"
                else:
                    output += f"Response: {error or 'Request failed'}\n\n"
            
            output += "==========================================\n\n"
        
        return output
    
    def save_results_to_file(
        self, 
        results: Dict[str, Any], 
        output_dir: Path, 
        bank_name: str,
        task_id: str
    ) -> Dict[str, str]:
        """Save UAT results to files with task_id naming format"""
        output_files = {}
        
        try:
            # Save formatted UAT results with task_id format
            uat_filename = f"uat_results_{task_id}.txt"
            uat_path = output_dir / uat_filename
            
            with open(uat_path, 'w', encoding='utf-8') as f:
                f.write("=" * 80 + "\n")
                f.write(f"{bank_name} API UAT Testing Results\n")
                f.write("=" * 80 + "\n\n")
                f.write(results["formatted_output"])
            
            output_files["uat_results"] = str(uat_path)
            
            # Save detailed results as JSON
            json_filename = f"uat_details_{task_id}.json"
            json_path = output_dir / json_filename
            
            with open(json_path, 'w', encoding='utf-8') as f:
                # Remove formatted_output from JSON to avoid duplication
                json_data = {k: v for k, v in results.items() if k != "formatted_output"}
                json.dump(json_data, f, indent=2, ensure_ascii=False, default=str)
            
            output_files["detailed_results"] = str(json_path)
            
            self.logger.info(f"UAT results saved to: {uat_path}")
            
        except Exception as e:
            self.logger.error(f"Failed to save UAT results: {str(e)}")
        
        return output_files