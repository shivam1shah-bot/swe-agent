# API Documentation Generator Agent

A specialized service for generating comprehensive API documentation from PDF bank specifications using AI-powered document analysis.

## 🎯 Purpose

The API Documentation Generator Agent focuses solely on **document processing and API documentation generation**. It takes PDF/document files as input and produces high-quality, structured API documentation ready for UAT testing.

## ✨ Features

### Core Capabilities

- **📄 Multi-Format Document Parsing**: PDF, TXT, DOC, DOCX support
- **🤖 AI-Powered Documentation**: Uses autonomous agents for intelligent content generation
- **🏦 Bank-Specific Context**: Enhanced prompts for different banks (HDFC, ICICI, Axis, etc.)
- **📊 Document Structure Analysis**: Automatic extraction of headers, sections, and technical details
- **📝 Multi-Format Output**: TXT, JSON, Markdown formats
- **✅ Quality Validation**: Ensures generated documentation meets professional standards

### Bank Support

Pre-configured context for major banks:

- HDFC Bank
- ICICI Bank
- Axis Bank
- State Bank of India (SBI)
- Yes Bank
- IDFC Bank
- And others with generic context

## 📋 Input Parameters

| Parameter            | Type    | Required | Description                                     |
| -------------------- | ------- | -------- | ----------------------------------------------- |
| `document_file_path` | string  | ✅       | Path to PDF/document file                       |
| `bank_name`          | string  | ✅       | Name of the bank for context enhancement        |
| `custom_prompt`      | string  | ❌       | Additional requirements for documentation       |
| `output_format`      | string  | ❌       | Output format: "txt", "json", "markdown", "all" |
| `include_examples`   | boolean | ❌       | Include code examples (default: true)           |
| `enhance_context`    | boolean | ❌       | Use bank-specific context (default: true)       |

## 📤 Output

### Response Structure

```json
{
  "status": "completed",
  "message": "API documentation generation completed successfully",
  "result": {
    "bank_name": "HDFC Bank",
    "output_format": "txt",
    "output_files": {
      "txt": "/path/to/HDFC_Bank_API_Documentation_20250109_143025.txt"
    },
    "file_contents": {
      "txt": "# HDFC Bank API Documentation\n\n..."
    },
    "document_statistics": {
      "total_lines": 1250,
      "sections_found": 8,
      "urls_found": 12,
      "api_endpoints_found": 15
    },
    "generation_metadata": {
      "processed_at": "2025-01-09T14:30:25",
      "include_examples": true,
      "enhanced_context": true
    }
  }
}
```

### Generated Documentation Features

- **Executive Summary**: Overview of API integration
- **Authentication & Security**: Auth methods and requirements
- **Endpoint Documentation**: Complete specifications with examples
- **Data Models**: Request/response schemas
- **Error Handling**: Error codes and responses
- **Integration Guidelines**: Best practices and implementation notes

## 🚀 Usage Examples

### Basic Usage

```bash
curl -X POST "http://localhost:8002/agents-catalogue/api-doc-generator" \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "document_file_path": "/path/to/hdfc_api_spec.pdf",
    "bank_name": "HDFC Bank"
  }'
```

### Advanced Usage with Custom Options

```bash
curl -X POST "http://localhost:8002/agents-catalogue/api-doc-generator" \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "document_file_path": "/path/to/bank_spec.pdf",
    "bank_name": "ICICI Bank",
    "custom_prompt": "Focus on corporate banking APIs with detailed security requirements",
    "output_format": "all",
    "include_examples": true,
    "enhance_context": true
  }'
```

### Python SDK Usage

```python
from src.services.agents_catalogue.api_doc_generator import APIDocGeneratorService

# Initialize service
service = APIDocGeneratorService()

# Generate documentation
result = service.execute({
    "document_file_path": "/path/to/bank_api_spec.pdf",
    "bank_name": "Axis Bank",
    "output_format": "markdown",
    "include_examples": True
})

print(f"Task ID: {result['task_id']}")
```

## 🔧 Installation

### Required Dependencies

```bash
# Core dependencies (usually already installed)
pip install fastapi pydantic

# Document parsing dependencies
pip install pdfplumber>=0.9.0  # For PDF parsing
pip install python-docx>=0.8.11  # For DOCX parsing (optional)
```

### Optional Dependencies

```bash
# Enhanced PDF parsing (alternative to pdfplumber)
pip install PyPDF2>=3.0.1

# Advanced document analysis
pip install nltk>=3.8.1
```

## 📁 File Structure

```
api_doc_generator/
├── __init__.py              # Package initialization
├── service.py               # Main APIDocGeneratorService
├── validator.py             # Parameter validation
├── document_parser.py       # PDF/document parsing
├── doc_generator.py         # AI documentation generation
└── README.md               # This file
```

## 🔗 Integration with Bank UAT Agent

The API Documentation Generator works seamlessly with the Bank UAT Agent:

1. **Generate Documentation**: Use this agent to create API docs from PDFs
2. **UAT Testing**: Pass generated documentation to `bank_uat_agent` for testing
3. **End-to-End Workflow**: Complete document → documentation → testing pipeline

```bash
# Step 1: Generate API documentation
TASK_1=$(curl -X POST ".../api-doc-generator" -d '{"document_file_path": "spec.pdf", "bank_name": "HDFC"}')

# Step 2: Use generated docs for UAT testing
curl -X POST ".../bank-uat-agent" \
  -d '{"api_doc_path": "/path/to/generated_docs.txt", "bank_name": "HDFC", "encryption_type": "rsa"}'
```

## 🎛️ Configuration

### Bank-Specific Context

The agent includes pre-configured context for major banks. You can extend this by modifying the `bank_contexts` in `doc_generator.py`:

```python
self.bank_contexts['new_bank'] = {
    'full_name': 'New Bank Ltd',
    'api_patterns': ['Custom API', 'Banking Gateway'],
    'auth_types': ['OAuth 2.0', 'API Key'],
    'common_endpoints': ['balance', 'transfer', 'inquiry']
}
```

### Output Customization

Customize documentation templates by modifying the prompts in `doc_generator.py`.

## 🚨 Error Handling

Common errors and solutions:

### Document Parsing Errors

```json
{
  "status": "failed",
  "message": "PDF parsing not available. Please install pdfplumber: pip install pdfplumber"
}
```

**Solution**: Install required dependencies

### File Access Errors

```json
{
  "status": "failed",
  "message": "Document file does not exist: /path/to/file.pdf"
}
```

**Solution**: Verify file path and permissions

### Documentation Generation Errors

```json
{
  "status": "failed",
  "message": "Generated documentation is too short or empty"
}
```

**Solution**: Check input document quality and autonomous agent availability

## 📊 Performance

- **Processing Time**: 2-5 minutes for typical bank API specifications
- **Document Size**: Supports files up to 50MB
- **Output Quality**: Professional-grade documentation ready for development teams

## 🔒 Security

- **File Validation**: Strict file type and size validation
- **Path Security**: Prevention of path traversal attacks
- **Content Sanitization**: Input sanitization for prompts and parameters
- **Temporary File Cleanup**: Automatic cleanup of processing files

---

**Next Step**: Use the generated API documentation with the [Bank UAT Agent](../bank_uat_agent/README.md) for comprehensive UAT testing with RSA encryption support.
