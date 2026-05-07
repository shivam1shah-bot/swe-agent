"""
Unit tests for UATExecutor class.

Tests the UAT execution engine for bank API testing with different encryption types
using mock certificate data for testing.
"""

import pytest
import json
import subprocess
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
from typing import Dict, Any, List, Optional

from src.services.agents_catalogue.bank_uat_agent.uat_executor import UATExecutor
from src.providers.logger import Logger
from src.providers.context import Context


class TestUATExecutor:
    """Test suite for UATExecutor class."""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test environment and mock logger."""
        self.mock_logger = Mock(spec=Logger)
        self.mock_ctx = Mock(spec=Context)
        self.executor = UATExecutor(logger=self.mock_logger)
        
        # Mock certificate contents for testing (no real certificate data)
        self.bank_cert_pem = "MOCK_BANK_CERTIFICATE_CONTENT"
        self.bank_private_key_pem = "MOCK_BANK_PRIVATE_KEY_CONTENT"
        self.service_public_key_pem = "MOCK_SERVICE_PUBLIC_KEY_CONTENT"
        self.service_private_key_pem = "MOCK_SERVICE_PRIVATE_KEY_CONTENT"
        
        # Sample curl commands for testing
        self.sample_curl_commands = [
            'curl -X POST "https://api.bank.com/transfer" -H "Content-Type: application/json" -d \'{"amount": 1000, "account": "12345"}\'',
            'curl -X GET "https://api.bank.com/balance" -H "Accept: application/json"',
            'curl -X POST "https://api.bank.com/payment" -H "Content-Type: application/json" -d \'{"merchant_id": "M123", "amount": 500}\''
        ]
        
        # Test AES key (256-bit hex)
        self.test_aes_key = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"

    def test_executor_initialization(self):
        """Test UATExecutor initialization."""
        # Test with custom logger
        executor = UATExecutor(logger=self.mock_logger)
        assert executor.logger == self.mock_logger
        assert executor.max_concurrent_requests == 5
        assert executor.default_timeout == 60
        assert executor.retry_attempts == 2
        
        # Test with default logger
        executor_default = UATExecutor()
        assert executor_default.logger is not None
        
        # Test crypto managers initialization
        assert executor.rsa_crypto is not None
        assert executor.aes_crypto is not None
        assert executor.response_analyzer is not None

    def test_setup_encryption_config_none(self):
        """Test encryption setup with no encryption."""
        config = self.executor._setup_encryption_config(
            encryption_type="none",
            public_key_pem=None,
            private_key_pem=None,
            generate_encrypted_curls=False
        )
        
        assert config["type"] == "none"
        assert config["generate_encrypted_curls"] is False
        assert config["validation"]["crypto_available"] is True
        assert config["validation"]["keys_validated"] is True
        assert config["validation"]["setup_successful"] is True

    def test_setup_encryption_config_rsa(self):
        """Test encryption setup with RSA encryption."""
        config = self.executor._setup_encryption_config(
            encryption_type="rsa",
            public_key_pem=self.service_public_key_pem,
            private_key_pem=self.service_private_key_pem,
            generate_encrypted_curls=True
        )
        
        assert config["type"] == "rsa"
        assert config["generate_encrypted_curls"] is True
        assert config["public_key"] == self.service_public_key_pem
        assert config["private_key"] == self.service_private_key_pem
        assert config["validation"]["crypto_available"] is True
        assert config["validation"]["setup_successful"] is True

    def test_setup_encryption_config_aes(self):
        """Test encryption setup with AES encryption."""
        config = self.executor._setup_encryption_config(
            encryption_type="aes",
            public_key_pem=None,
            private_key_pem=None,
            generate_encrypted_curls=True
        )
        
        assert config["type"] == "aes"
        assert config["generate_encrypted_curls"] is True
        assert config["validation"]["crypto_available"] is True
        assert config["validation"]["setup_successful"] is True

    def test_setup_encryption_config_hybrid(self):
        """Test encryption setup with hybrid (RSA+AES) encryption."""
        config = self.executor._setup_encryption_config(
            encryption_type="hybrid",
            public_key_pem=self.service_public_key_pem,
            private_key_pem=self.service_private_key_pem,
            generate_encrypted_curls=True
        )
        
        assert config["type"] == "hybrid"
        assert config["generate_encrypted_curls"] is True
        assert config["public_key"] == self.service_public_key_pem
        assert config["private_key"] == self.service_private_key_pem
        assert config["validation"]["crypto_available"] is True
        assert config["validation"]["setup_successful"] is True

    def test_setup_encryption_config_signature_only(self):
        """Test encryption setup with signature-only mode."""
        config = self.executor._setup_encryption_config(
            encryption_type="signature_only",
            public_key_pem=None,
            private_key_pem=self.service_private_key_pem,
            generate_encrypted_curls=True
        )
        
        assert config["type"] == "signature_only"
        assert config["generate_encrypted_curls"] is True
        assert config["private_key"] == self.service_private_key_pem
        assert config["validation"]["crypto_available"] is True
        assert config["validation"]["keys_validated"] is True
        assert config["validation"]["setup_successful"] is True

    def test_setup_encryption_config_rsa_missing_public_key(self):
        """Test encryption setup with RSA but missing public key."""
        config = self.executor._setup_encryption_config(
            encryption_type="rsa",
            public_key_pem=None,
            private_key_pem=self.service_private_key_pem,
            generate_encrypted_curls=True
        )
        
        assert config["type"] == "rsa"
        assert "error" in config["validation"]
        assert "RSA public key required" in config["validation"]["error"]
        assert config["validation"]["setup_successful"] is False

    def test_clean_curl_command(self):
        """Test curl command cleaning and preparation."""
        # Test with line continuations
        dirty_curl = "curl -X POST \\\n  'https://api.com' \\\n  -d 'data'"
        cleaned = self.executor._clean_curl_command(dirty_curl)
        assert "\\\n" not in cleaned
        assert cleaned.startswith("curl")
        
        # Test without curl prefix
        no_curl = "-X POST 'https://api.com'"
        cleaned = self.executor._clean_curl_command(no_curl)
        assert cleaned.startswith("curl")
        
        # Test normal curl
        normal_curl = "curl -X GET 'https://api.com'"
        cleaned = self.executor._clean_curl_command(normal_curl)
        assert cleaned == normal_curl

    def test_looks_like_encrypted_response(self):
        """Test encrypted response detection."""
        # Test base64-like encrypted response
        encrypted_base64 = "YWJjZGVmZ2hpams0NTZhYmNkZWZnaGlqazQ1NmFiY2RlZmdoaWprNDU2"
        assert self.executor._looks_like_encrypted_response(encrypted_base64) is True
        
        # Test JSON with encrypted fields
        encrypted_json = '{"encrypted_data": "abc123", "status": "success"}'
        assert self.executor._looks_like_encrypted_response(encrypted_json) is True
        
        # Test plain response
        plain_response = '{"balance": 1000, "status": "success"}'
        assert self.executor._looks_like_encrypted_response(plain_response) is False
        
        # Test empty/short response
        assert self.executor._looks_like_encrypted_response("") is False
        assert self.executor._looks_like_encrypted_response("ok") is False

    @patch('subprocess.run')
    def test_execute_curl_with_retry_success(self, mock_subprocess):
        """Test successful curl execution with retry logic."""
        # Mock successful subprocess execution
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = '{"balance": 1000, "status": "success"}'
        mock_result.stderr = ""
        mock_subprocess.return_value = mock_result
        
        curl_command = 'curl -X GET "https://api.bank.com/balance"'
        response = self.executor._execute_curl_with_retry(curl_command, 30)
        
        assert response == '{"balance": 1000, "status": "success"}'
        mock_subprocess.assert_called_once()

    @patch('subprocess.run')
    def test_execute_curl_with_retry_failure(self, mock_subprocess):
        """Test curl execution with retry on failure."""
        # Mock failing subprocess execution
        mock_subprocess.side_effect = subprocess.CalledProcessError(
            1, "curl", "Failed", "Connection failed"
        )
        
        curl_command = 'curl -X GET "https://api.bank.com/balance"'
        
        with pytest.raises(subprocess.CalledProcessError):
            self.executor._execute_curl_with_retry(curl_command, 30)
        
        # Should retry default number of times + 1 initial attempt
        assert mock_subprocess.call_count == self.executor.retry_attempts + 1

    @patch('subprocess.run')
    def test_execute_curl_with_retry_timeout(self, mock_subprocess):
        """Test curl execution timeout handling."""
        # Mock timeout exception
        mock_subprocess.side_effect = subprocess.TimeoutExpired("curl", 30)
        
        curl_command = 'curl -X GET "https://api.bank.com/balance"'
        
        with pytest.raises(subprocess.TimeoutExpired):
            self.executor._execute_curl_with_retry(curl_command, 30)

    def test_decrypt_response_none_encryption(self):
        """Test response decryption with no encryption."""
        crypto_config = {
            "type": "none",
            "generate_encrypted_curls": False
        }
        
        response = '{"balance": 1000}'
        result = self.executor._decrypt_response(response, crypto_config)
        assert result is None  # No decryption attempted

    def test_decrypt_response_signature_only(self):
        """Test response decryption with signature-only mode."""
        crypto_config = {
            "type": "signature_only",
            "generate_encrypted_curls": True
        }
        
        response = '{"balance": 1000, "signature": "abc123"}'
        result = self.executor._decrypt_response(response, crypto_config)
        assert result == response.strip()  # Returns as-is for signature-only

    @patch('src.services.agents_catalogue.bank_uat_agent.uat_executor.UATExecutor._execute_curl_with_retry')
    def test_execute_single_curl_success(self, mock_curl_retry):
        """Test successful execution of a single curl command."""
        # Mock successful curl execution
        mock_curl_retry.return_value = '{"transfer_id": "T123", "status": "success"}'
        
        crypto_config = {
            "type": "none",
            "generate_encrypted_curls": False,
            "validation": {"crypto_available": False}
        }
        
        result = self.executor._execute_single_curl(
            curl_command=self.sample_curl_commands[0],
            test_number=1,
            bank_name="TestBank",
            crypto_config=crypto_config,
            timeout_seconds=30,
            include_response_analysis=False,
            ctx=self.mock_ctx
        )
        
        assert result["test_number"] == 1
        assert result["status"] == "success"
        assert result["curl_command"] == self.sample_curl_commands[0]
        assert result["response_data"] == '{"transfer_id": "T123", "status": "success"}'
        assert result["execution_time"] >= 0

    @patch('src.services.agents_catalogue.bank_uat_agent.uat_executor.UATExecutor._execute_curl_with_retry')
    def test_execute_single_curl_with_response_analysis(self, mock_curl_retry):
        """Test curl execution with response analysis enabled."""
        # Mock successful curl execution
        mock_curl_retry.return_value = '{"balance": 1000, "currency": "INR"}'
        
        # Mock response analyzer
        mock_analysis = {
            "response_type": "json",
            "fields_detected": ["balance", "currency"],
            "encryption_detected": False
        }
        self.executor.response_analyzer.analyze_response = Mock(return_value=mock_analysis)
        
        crypto_config = {
            "type": "none",
            "generate_encrypted_curls": False,
            "validation": {"crypto_available": False}
        }
        
        result = self.executor._execute_single_curl(
            curl_command=self.sample_curl_commands[1],
            test_number=2,
            bank_name="TestBank",
            crypto_config=crypto_config,
            timeout_seconds=30,
            include_response_analysis=True,
            ctx=self.mock_ctx
        )
        
        assert result["status"] == "success"
        assert result["analysis"] == mock_analysis
        self.executor.response_analyzer.analyze_response.assert_called_once()

    def test_calculate_performance_metrics(self):
        """Test performance metrics calculation."""
        test_results = [
            {"status": "success", "execution_time": 1.5},
            {"status": "success", "execution_time": 2.0},
            {"status": "failed", "execution_time": 0.5},
            {"status": "timeout", "execution_time": 30.0}
        ]
        
        metrics = self.executor._calculate_performance_metrics(test_results)
        
        assert metrics["total_tests"] == 4
        assert metrics["successful_tests"] == 2
        assert metrics["failed_tests"] == 1
        assert metrics["timeout_tests"] == 1
        assert metrics["success_rate"] == 50.0
        assert metrics["performance"]["min_execution_time"] == 0.5
        assert metrics["performance"]["max_execution_time"] == 30.0
        assert metrics["performance"]["avg_execution_time"] == 8.5
        assert metrics["performance"]["total_execution_time"] == 34.0

    def test_format_uat_output_no_encryption(self):
        """Test UAT output formatting without encryption."""
        test_results = [
            {
                "test_number": 1,
                "curl_command": self.sample_curl_commands[0],
                "status": "success",
                "response_data": '{"status": "success"}',
                "error": None
            }
        ]
        
        output = self.executor._format_uat_output(
            test_results=test_results,
            bank_name="TestBank",
            encryption_type="none",
            generate_encrypted_curls=False
        )
        
        assert "UAT Testing Results (No Encryption)" in output
        assert "TestBank" in output
        assert "Test 1" in output
        assert self.sample_curl_commands[0] in output
        assert '{"status": "success"}' in output

    def test_format_uat_output_with_encryption(self):
        """Test UAT output formatting with encryption."""
        test_results = [
            {
                "test_number": 1,
                "curl_command": self.sample_curl_commands[0],
                "status": "success",
                "response_data": "encrypted_response_data",
                "decrypted_response": '{"status": "success"}',
                "error": None
            }
        ]
        
        output = self.executor._format_uat_output(
            test_results=test_results,
            bank_name="TestBank",
            encryption_type="hybrid",
            generate_encrypted_curls=True
        )
        
        assert "UAT Testing Results (With RSA Encryption)" in output
        assert "1. Original cURL Command (Non-Encrypted Request)" in output
        assert "2. Encrypted cURL Command (Encrypted Request)" in output
        assert "3. Encrypted Response" in output
        assert "4. Decrypted Response" in output

    @patch('src.services.agents_catalogue.bank_uat_agent.uat_executor.UATExecutor._execute_curl_commands_sequential')
    def test_execute_uat_tests_integration(self, mock_sequential_execution):
        """Test full UAT execution integration."""
        # Mock sequential execution results
        mock_results = [
            {
                "test_number": 1,
                "curl_command": self.sample_curl_commands[0],
                "status": "success",
                "response_data": '{"transfer_id": "T123"}',
                "execution_time": 1.5
            }
        ]
        mock_sequential_execution.return_value = mock_results
        
        # Execute UAT tests
        results = self.executor.execute_uat_tests(
            curl_commands=self.sample_curl_commands[:1],
            bank_name="TestBank",
            encryption_type="none",
            public_key_pem=None,
            private_key_pem=None,
            timeout_seconds=30,
            include_response_analysis=False,
            custom_headers=None,
            generate_encrypted_curls=False,
            ctx=self.mock_ctx
        )
        
        # Verify results structure
        assert "execution_summary" in results
        assert "crypto_validation" in results
        assert "test_results" in results
        assert "performance_metrics" in results
        assert "formatted_output" in results
        
        # Verify execution summary
        summary = results["execution_summary"]
        assert summary["bank_name"] == "TestBank"
        assert summary["encryption_type"] == "none"
        assert summary["total_commands"] == 1
        assert "execution_time_seconds" in summary
        assert "timestamp" in summary

    def test_execute_uat_tests_with_rsa_encryption(self):
        """Test UAT execution with RSA encryption setup."""
        with patch('src.services.agents_catalogue.bank_uat_agent.uat_executor.UATExecutor._execute_curl_commands_sequential') as mock_sequential:
            mock_sequential.return_value = []
            
            results = self.executor.execute_uat_tests(
                curl_commands=self.sample_curl_commands[:1],
                bank_name="TestBank",
                encryption_type="rsa",
                public_key_pem=self.service_public_key_pem,
                private_key_pem=self.service_private_key_pem,
                timeout_seconds=30,
                generate_encrypted_curls=True,
                ctx=self.mock_ctx
            )
            
            # Verify crypto validation
            crypto_validation = results["crypto_validation"]
            assert crypto_validation["crypto_available"] is True
            assert crypto_validation["setup_successful"] is True

    def test_execute_uat_tests_with_hybrid_encryption(self):
        """Test UAT execution with hybrid (RSA+AES) encryption setup."""
        with patch('src.services.agents_catalogue.bank_uat_agent.uat_executor.UATExecutor._execute_curl_commands_sequential') as mock_sequential:
            mock_sequential.return_value = []
            
            results = self.executor.execute_uat_tests(
                curl_commands=self.sample_curl_commands[:1],
                bank_name="TestBank",
                encryption_type="hybrid",
                public_key_pem=self.service_public_key_pem,
                private_key_pem=self.service_private_key_pem,
                timeout_seconds=30,
                generate_encrypted_curls=True,
                ctx=self.mock_ctx
            )
            
            # Verify execution summary
            assert results["execution_summary"]["encryption_type"] == "hybrid"
            
            # Verify crypto validation
            crypto_validation = results["crypto_validation"]
            assert crypto_validation["crypto_available"] is True
            assert crypto_validation["setup_successful"] is True

    def test_save_results_to_file(self, tmp_path):
        """Test saving UAT results to files."""
        # Create test results
        test_results = {
            "execution_summary": {
                "bank_name": "TestBank",
                "encryption_type": "none",
                "total_commands": 1
            },
            "test_results": [
                {
                    "test_number": 1,
                    "status": "success",
                    "response_data": '{"status": "ok"}'
                }
            ],
            "formatted_output": "=== Test Results ===\nTest completed successfully."
        }
        
        # Save results
        output_files = self.executor.save_results_to_file(
            results=test_results,
            output_dir=tmp_path,
            bank_name="TestBank",
            task_id="test_task_123"
        )
        
        # Verify files were created
        assert "uat_results" in output_files
        assert "detailed_results" in output_files
        
        # Verify file contents
        uat_file = Path(output_files["uat_results"])
        assert uat_file.exists()
        assert "TestBank" in uat_file.read_text()
        
        json_file = Path(output_files["detailed_results"])
        assert json_file.exists()
        json_data = json.loads(json_file.read_text())
        assert json_data["execution_summary"]["bank_name"] == "TestBank"

    def test_decrypt_response_with_aes_default_key(self):
        """Test response decryption with AES using default key (current limitation)."""
        crypto_config = {
            "type": "aes",
            "generate_encrypted_curls": True
        }
        
        # Mock AES crypto to simulate decryption
        mock_decrypted = '{"original": "data"}'
        self.executor.aes_crypto.looks_like_encrypted_response = Mock(return_value=True)
        self.executor.aes_crypto.decrypt_payload = Mock(return_value=mock_decrypted)
        
        encrypted_response = "base64_encrypted_data"
        result = self.executor._decrypt_response(encrypted_response, crypto_config)
        
        # Verify decryption was attempted with default key
        self.executor.aes_crypto.decrypt_payload.assert_called_once_with(
            encrypted_response, self.executor.aes_crypto.DEFAULT_HEX_KEY
        )
        assert result == mock_decrypted

    def test_concurrent_execution_configuration(self):
        """Test that concurrent execution configuration is properly set."""
        assert self.executor.max_concurrent_requests == 5
        assert self.executor.default_timeout == 60
        assert self.executor.retry_attempts == 2
        assert self.executor.retry_delay == 1.0

    def test_error_handling_in_single_curl_execution(self):
        """Test error handling in single curl execution."""
        crypto_config = {
            "type": "none",
            "generate_encrypted_curls": False,
            "validation": {"crypto_available": False}
        }
        
        # Test timeout error
        with patch('src.services.agents_catalogue.bank_uat_agent.uat_executor.UATExecutor._execute_curl_with_retry') as mock_curl:
            mock_curl.side_effect = subprocess.TimeoutExpired("curl", 30)
            
            result = self.executor._execute_single_curl(
                curl_command=self.sample_curl_commands[0],
                test_number=1,
                bank_name="TestBank",
                crypto_config=crypto_config,
                timeout_seconds=30,
                include_response_analysis=False,
                ctx=self.mock_ctx
            )
            
            assert result["status"] == "timeout"
            assert "timed out" in result["error"]

        # Test process error
        with patch('src.services.agents_catalogue.bank_uat_agent.uat_executor.UATExecutor._execute_curl_with_retry') as mock_curl:
            mock_curl.side_effect = subprocess.CalledProcessError(1, "curl", "", "Connection failed")
            
            result = self.executor._execute_single_curl(
                curl_command=self.sample_curl_commands[0],
                test_number=1,
                bank_name="TestBank",
                crypto_config=crypto_config,
                timeout_seconds=30,
                include_response_analysis=False,
                ctx=self.mock_ctx
            )
            
            assert result["status"] == "error"
            assert "exit code 1" in result["error"]

        # Test general exception
        with patch('src.services.agents_catalogue.bank_uat_agent.uat_executor.UATExecutor._execute_curl_with_retry') as mock_curl:
            mock_curl.side_effect = Exception("Network error")
            
            result = self.executor._execute_single_curl(
                curl_command=self.sample_curl_commands[0],
                test_number=1,
                bank_name="TestBank",
                crypto_config=crypto_config,
                timeout_seconds=30,
                include_response_analysis=False,
                ctx=self.mock_ctx
            )
            
            assert result["status"] == "failed"
            assert result["error"] == "Network error" 