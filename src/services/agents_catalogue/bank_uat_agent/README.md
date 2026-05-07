# Bank UAT Agent

A specialized service for comprehensive UAT testing of bank API integrations with **AI-powered URL extraction** and advanced encryption support including RSA and AES.

## 🎯 Purpose

The Bank UAT Agent focuses on **API testing and validation** using existing API documentation. It leverages **Artificial Intelligence** for intelligent URL extraction and supports modern RSA encryption with public/private keys alongside legacy AES encryption for comprehensive testing scenarios.

## ✨ Features

### Core UAT Capabilities

- **🤖 AI-Powered URL Extraction**: Uses autonomous agents to intelligently parse API documentation
- **📋 Smart Documentation Analysis**: Parses existing API documentation (TXT, JSON, MD, PDF)
- **🔧 Intelligent Curl Generation**: Creates comprehensive test scenarios using AI
- **⚡ Advanced UAT Execution**: Multi-scenario testing (success, error, boundary, security)
- **📊 Response Analysis**: Detailed response parsing and validation
- **🔄 Multi-Format Support**: Handles various API documentation formats

### 🔐 Advanced Encryption Support

#### RSA Encryption (New!)

- **Public/Private Key Support**: Full RSA key pair management
- **Hybrid Encryption**: RSA + AES for large payloads
- **Key Validation**: Automatic key pair validation
- **Multiple Key Formats**: PEM, CRT, KEY file support

#### AES Encryption (Legacy Compatible)

- **UAT_LangGraph Compatible**: 100% backward compatibility
- **Dynamic IV Generation**: ASCII 47-126 range matching original
- **Custom Crypto Specs**: Support for custom encryption specifications

#### Encryption Types

| Type     | Description           | Use Case                         |
| -------- | --------------------- | -------------------------------- |
| `rsa`    | Pure RSA encryption   | Small payloads, high security    |
| `aes`    | Legacy AES encryption | UAT_LangGraph compatibility      |
| `hybrid` | RSA + AES combination | Large payloads with RSA security |
| `none`   | No encryption         | Plain text testing               |

## 🤖 AI Integration

### AI-Powered Components

- **URL Extraction**: AI analyzes API documentation to extract endpoints
- **cURL Generation**: AI generates test scenarios for each endpoint
- **Context Awareness**: AI understands bank-specific patterns and requirements
- **Intelligent Parsing**: No hardcoded regex patterns, pure AI understanding

### AI Usage Scenarios

1. **API Documentation Analysis**: AI extracts URLs and combines with UAT host
2. **Test Scenario Generation**: AI creates appropriate cURL commands for each scenario
3. **Context Enhancement**: AI incorporates bank-specific knowledge and custom requirements

### AI Workflow

```
API Documentation → AI Analysis → URL Extraction → AI cURL Generation → Test Execution
```

## 📋 Input Parameters

| Parameter                  | Type    | Required | Description                                           |
| -------------------------- | ------- | -------- | ----------------------------------------------------- |
| `api_doc_path`             | string  | ✅       | Path to API documentation file                        |
| `bank_name`                | string  | ✅       | Name of the bank for context                          |
| `uat_host`                 | string  | ✅       | UAT environment host URL                              |
| `public_key_path`          | string  | ❌       | Path to RSA public key file (.pem, .crt, .key)        |
| `private_key_path`         | string  | ❌       | Path to RSA private key file (for decryption)         |
| `encryption_type`          | string  | ❌       | "rsa", "aes", "hybrid", "none" (default: "aes")       |
| `generate_encrypted_curls` | boolean | ❌       | Enable encryption in generated cURLs (default: false) |
| `apis_to_test`             | array   | ❌       | Specific APIs to focus on                             |

| `timeout_seconds` | integer | ❌ | Request timeout (10-300, default: 60) |
| `include_response_analysis` | boolean | ❌ | Enable detailed response analysis (default: true) |
| `custom_headers` | object | ❌ | Additional HTTP headers |
| `custom_prompt` | string | ❌ | Custom instructions for AI generation |

## 🔄 Request Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           BANK UAT AGENT WORKFLOW                              │
└─────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────┐    ┌──────────────────┐    ┌──────────────────┐
│   User Input    │    │  API Document    │    │  Encryption      │
│                 │    │   Upload         │    │     Keys         │
│ • Bank Name     │───▶│ • TXT/PDF/MD     │───▶│ • Public Key     │
│ • UAT Host      │    │ • JSON Format    │    │ • Private Key    │
│ • Test Scenarios│    │ • API Specs      │    │ • Key Validation │
│ • Custom Headers│    │ • Endpoints      │    │ • Auto-enable    │
└─────────────────┘    └──────────────────┘    └──────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              AI-POWERED PROCESSING                              │
└─────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────┐    ┌──────────────────┐    ┌──────────────────┐
│  AI URL         │    │  AI cURL         │    │  AI Context      │
│  Extraction     │    │  Generation      │    │  Enhancement     │
│                 │    │                 │    │                 │
│ • Parse Doc     │───▶│ • Success Tests │───▶│ • Bank Context   │
│ • Extract URLs  │    │ • Error Tests   │    │ • Custom Prompts │
│ • Apply UAT Host│    │ • Boundary Tests│    │ • Headers        │
│ • JSON Output   │    │ • Security Tests│    │ • Requirements   │
└─────────────────┘    └──────────────────┘    └──────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              EXECUTION & ANALYSIS                               │
└─────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────┐    ┌──────────────────┐    ┌──────────────────┐
│  cURL           │    │  Response        │    │  Result          │
│  Execution      │    │  Processing      │    │  Generation      │
│                 │    │                 │    │                 │
│ • Parallel Exec │───▶│ • Decryption     │───▶│ • Test Reports   │
│ • Timeout Mgmt  │    │ • Analysis       │    │ • Performance    │
│ • Retry Logic   │    │ • Validation     │    │ • cURL Commands  │
│ • Error Handling│    │ • Formatting     │    │ • Encryption     │
└─────────────────┘    └──────────────────┘    └──────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                                 OUTPUT FILES                                    │
└─────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────┐    ┌──────────────────┐    ┌──────────────────┐
│  UAT Results    │    │  cURL Commands   │    │  Detailed JSON   │
│                 │    │                 │    │                 │
│ • Test Summary  │    │ • Generated      │    │ • Full Results   │
│ • Performance   │    │ • Executable     │    │ • Metadata       │
│ • Success Rate  │    │ • Scenario-based │    │ • Analysis       │
│ • Error Details │    │ • Ready to Use   │    │ • Encryption     │
└─────────────────┘    └──────────────────┘    └──────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────┐
│                              KEY AI INTERACTIONS                                │
└─────────────────────────────────────────────────────────────────────────────────┘

🤖 AI Agent 1: URL Extraction
   Input: API Documentation + UAT Host + Bank Context
   Output: Structured JSON with endpoint names and complete URLs
   Purpose: Intelligent parsing without hardcoded patterns

🤖 AI Agent 2: cURL Generation
   Input: Endpoint URLs + Test Scenarios + Custom Requirements
   Output: Executable cURL commands for each scenario
   Purpose: Context-aware test generation

🔐 Encryption Flow:
   • AI generates PLAIN cURL commands (no encryption)
   • System handles encryption/decryption separately
   • AI focuses on test logic, not crypto complexity
```

## 📤 Output

### Response Structure

```json
{
  "status": "completed",
  "message": "Bank UAT testing completed successfully",
  "result": {
    "bank_name": "HDFC Bank",
    "uat_host": "http://127.0.0.1:8081",
    "encryption_type": "rsa",
    "generate_encrypted_curls": true,
    "total_tests_executed": 15,
    "test_results": {
      "success_count": 12,
      "error_count": 2,
      "timeout_count": 1
    },
    "output_files": {
      "uat_results": "/path/to/UAT_Results_HDFC_20250109_143025.txt",
      "curl_commands": "/path/to/curl_commands_<task_id>.txt"
    },
    "file_contents": {
      "uat_results": "=== UAT Testing Results (With RSA Encryption) ===\n\n..."
    },
    "encryption_metadata": {
      "public_key_loaded": true,
      "private_key_loaded": true,
      "keys_are_real": true,
      "key_source": "provided",
      "crypto_validation": "passed"
    },
    "execution_summary": {
      "total_commands": 15,
      "execution_time_seconds": 45.2
    },
    "urls_extracted": 8,
    "curl_commands_generated": 15
  }
}
```

### Test Result Format

```
=== UAT Testing Results (With RSA Encryption) ===

Bank: HDFC Bank
Generated on: 2025-01-09 14:30:25
UAT Host: http://127.0.0.1:8081
Encryption Type: rsa
Generate Encrypted Curls: true
Key Source: provided
Keys are Real: true

--- Test 1: balance_inquiry (success) ---
1. cURL Command:
curl -X POST "http://127.0.0.1:8081/v1/balance_inquiry" \
  -H "Content-Type: application/json" \
  -d '{"account_number": "123456789", "customer_id": "CUST001"}'

2. Response Status: success
3. Execution Time: 1.2s
4. Response Analysis: Valid JSON response with balance information

==========================================
```

## 🚀 Usage Examples

### Basic UAT Testing with AI

```bash
curl -X POST "http://localhost:28002/agents-catalogue/bank-uat-agent" \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "api_doc_path": "/path/to/yes_bank_api_docs.txt",
    "bank_name": "Yes Bank",
    "uat_host": "http://127.0.0.1:8081",
    "encryption_type": "aes",

    "custom_headers": {
      "X-API-Version": "1.0",
      "X-Client-ID": "test-client"
    }
  }'
```

### RSA Encryption Testing with AI

```bash
curl -X POST "http://localhost:28002/agents-catalogue/bank-uat-agent" \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "api_doc_path": "/path/to/hdfc_api_docs.txt",
    "bank_name": "HDFC Bank",
    "uat_host": "http://127.0.0.1:8081",
    "encryption_type": "rsa",
    "public_key_path": "/path/to/hdfc_public.pem",
    "private_key_path": "/path/to/hdfc_private.pem",
    "generate_encrypted_curls": true,
    "apis_to_test": ["fund_transfer", "balance_inquiry"],

  }'
```

### AI-Enhanced Testing with Custom Prompts

```bash
curl -X POST "http://localhost:28002/agents-catalogue/bank-uat-agent" \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "api_doc_path": "/path/to/icici_api_docs.txt",
    "bank_name": "ICICI Bank",
    "uat_host": "http://127.0.0.1:8081",
    "encryption_type": "hybrid",
    "public_key_path": "/path/to/icici_public.pem",
    "private_key_path": "/path/to/icici_private.pem",
    "custom_prompt": "Focus on payment gateway APIs and include transaction validation tests",

    "timeout_seconds": 120
  }'
```

## 📁 File Structure

```
bank_uat_agent/
├── __init__.py              # Package initialization
├── service.py               # Main BankUATService with AI workflow
├── validator.py             # Parameter validation
├── curl_generator.py        # AI-powered URL extraction and cURL generation
├── uat_executor.py          # Test execution engine (no AI)
├── rsa_crypto_manager.py    # RSA encryption/decryption
├── aes_crypto_manager.py    # AES encryption (legacy)
├── response_analyzer.py     # Response analysis
└── README.md               # This file
```

## 🔐 Encryption Details

### AI vs Traditional Processing

- **AI Handles**: URL extraction, cURL generation, context understanding
- **Traditional Handles**: Encryption/decryption, HTTP execution, response processing
- **Separation**: AI focuses on intelligence, crypto managers handle security

### RSA Key Management

```python
from bank_uat_agent.rsa_crypto_manager import RSACryptoManager

# Generate new key pair
rsa_manager = RSACryptoManager()
public_pem, private_pem = rsa_manager.generate_rsa_keypair(2048)

# Load existing keys
public_key = rsa_manager.load_public_key("/path/to/public.pem")
private_key = rsa_manager.load_private_key("/path/to/private.pem")

# Validate key pair
is_valid = rsa_manager.validate_rsa_keys(public_key, private_key)
```

### Encryption Flow

1. **AI Generation**: Creates plain cURL commands
2. **Request Execution**: System executes commands via subprocess
3. **Response Processing**: System detects encrypted responses
4. **Decryption**: Uses appropriate crypto manager to decrypt
5. **Analysis**: Processes decrypted responses for validation

## 📊 Test Scenarios

### AI-Generated Test Types

- **Comprehensive Testing**: Multiple test variations for each endpoint
- **Valid Requests**: Proper parameters with realistic test data
- **Error Handling**: Invalid parameters, missing fields, auth failures
- **Edge Cases**: Boundary values, large payloads, format variations

### AI Context Enhancement

- **Bank-Specific Patterns**: Recognizes bank API conventions
- **Custom Requirements**: Incorporates user-specified testing needs
- **Header Management**: Intelligently applies custom headers
- **Endpoint Adaptation**: Adjusts tests based on endpoint characteristics

## 🔗 Integration Workflow

### Complete AI-Powered Pipeline

```bash
# Step 1: Upload API documentation
curl -X POST ".../files/upload-file" \
  -F "file=@bank_spec.pdf" \
  -F "file_type=bank_document"

# Step 2: Execute UAT with AI-powered extraction
curl -X POST ".../bank-uat-agent" \
  -d '{
    "api_doc_path": "/uploads/bank_uat_agent/documents/bank_spec.pdf",
    "bank_name": "Yes Bank",
    "uat_host": "http://127.0.0.1:8081",
    "encryption_type": "aes",

  }'
```

## 🚨 Error Handling

### AI-Specific Errors

```json
{
  "status": "failed",
  "message": "AI URL extraction failed: No URLs extracted from documentation"
}
```

### Encryption Errors

```json
{
  "status": "failed",
  "message": "RSA encryption not available. Please install cryptography: pip install cryptography"
}
```

### Key Validation Errors

```json
{
  "status": "failed",
  "message": "Public key file does not exist: /path/to/key.pem"
}
```

## 📈 Performance

- **AI Processing**: 1-2 minutes for URL extraction and cURL generation
- **Test Execution**: 2-6 minutes depending on test complexity and count
- **Total Time**: 3-8 minutes for complete workflow
- **Concurrent Tests**: Supports parallel execution with configurable limits
- **Memory Usage**: Efficient processing with temporary file cleanup

## 🔒 Security Features

- **AI Isolation**: AI agents don't receive encryption keys or certificates
- **Key Validation**: Automatic RSA key pair validation
- **Secure Cleanup**: Automatic cleanup of temporary encryption files
- **Path Security**: Prevention of path traversal attacks
- **Input Sanitization**: Comprehensive parameter validation
- **Encryption Strength**: RSA-2048 and AES-256 support

## 🤖 AI Agent Details

### Autonomous Agent Integration

- **Component**: `src.tools.autonomous_agent.AutonomousAgent`
- **Context**: Full execution context for correlation and logging
- **Error Handling**: Comprehensive error handling for AI failures
- **No Fallbacks**: System fails fast with clear error messages

### AI Prompt Engineering

- **UAT Host Priority**: AI is explicitly instructed to use only specified UAT host
- **Bank Context**: AI receives bank-specific information for better understanding
- **Custom Requirements**: User-specified custom prompts are incorporated
- **Test Instructions**: Clear instructions for comprehensive testing

### AI Response Validation

- **JSON Parsing**: Ensures AI responses are valid JSON
- **URL Validation**: Validates that generated URLs are properly formatted
- **cURL Validation**: Ensures generated commands are executable
- **Error Reporting**: Comprehensive error reporting for AI failures
