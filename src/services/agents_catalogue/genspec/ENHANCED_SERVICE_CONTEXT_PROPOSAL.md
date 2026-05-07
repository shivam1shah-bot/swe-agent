# Enhanced Service Context Proposal

## Problem

Current implementation only fetches README files, which often contain:

- Generic boilerplate documentation
- Folder structure descriptions
- Build instructions
- Minimal technical details about actual service functionality

## Proposed Enhancements

### 1. **Multi-Source Context Gathering** (Priority: HIGH)

Instead of just README, fetch:

```python
class EnhancedServiceContext:
    sources = [
        "README.md",           # Overview
        "API.md",              # API documentation
        "ARCHITECTURE.md",     # Architecture details
        "docs/api-spec.yaml",  # OpenAPI/Swagger specs
        "docs/integration.md", # Integration patterns
        "CONTRIBUTING.md"      # Development patterns
    ]
```

**Implementation:**

- Try multiple documentation files
- Parse OpenAPI/Swagger specs for API details
- Extract from docs/ folder

### 2. **Confluence/Wiki Integration** (Priority: HIGH)

Many services have detailed documentation in Confluence:

```python
def fetch_confluence_docs(service_name):
    """
    Fetch service documentation from Razorpay Confluence

    Searches for:
    - Service architecture pages
    - API documentation
    - Integration guides
    - Runbooks
    """
    confluence_client = ConfluenceClient(config["confluence"])
    pages = confluence_client.search(f"space=ENG AND title~'{service_name}'")
    return aggregate_content(pages)
```

**Benefits:**

- More comprehensive technical details
- Architecture diagrams
- Integration patterns
- Real-world usage examples

### 3. **Code Analysis** (Priority: MEDIUM)

Analyze the actual codebase:

```python
def analyze_service_code(repo_url):
    """
    Extract technical details from code:
    - API endpoints (from route definitions)
    - Database models
    - External service calls
    - Message queue patterns
    - Configuration structure
    """
    return {
        "api_endpoints": extract_endpoints(code),
        "database_tables": extract_models(code),
        "dependencies": extract_dependencies(code),
        "queue_consumers": extract_queue_handlers(code),
        "external_services": extract_external_calls(code)
    }
```

**Tools:**

- Use existing context_generator tool for code analysis
- Parse API route definitions
- Extract database schemas from models
- Identify integration patterns

### 4. **Structured Service Metadata** (Priority: HIGH)

Create a service registry with structured metadata:

```yaml
# services/merchant_invoice.yaml
service_name: merchant_invoice
description: "Merchant invoice generation and management service"
type: microservice
tech_stack:
  language: Go
  framework: go-foundation
  database: MySQL
  queue: SQS

apis:
  - endpoint: POST /invoices
    description: Create merchant invoice
    authentication: JWT
  - endpoint: GET /invoices/{id}
    description: Fetch invoice details

integrations:
  - service: api
    purpose: Merchant data fetching
    protocol: REST
  - service: scrooge
    purpose: Pricing and discount calculation
    protocol: gRPC

database_tables:
  - name: invoices
    description: Main invoice table
    schema_url: https://github.com/razorpay/merchant_invoice/blob/main/migrations/001_invoices.sql

message_queues:
  publishes:
    - queue: invoice_created
      event: InvoiceCreatedEvent
  subscribes:
    - queue: payment_received
      handler: UpdateInvoiceStatus

deployment:
  repository: razorpay/merchant_invoice
  owners: ["merchant-platform-team"]
  on_call: "@merchant-platform-oncall"
```

**Benefits:**

- Consistent, structured information
- Easy to maintain
- Machine-readable
- Comprehensive technical details

### 5. **API Specification Parsing** (Priority: MEDIUM)

If service has OpenAPI/Swagger specs:

```python
def parse_api_spec(repo_url):
    """
    Parse OpenAPI/Swagger specification

    Returns:
    - All endpoints with request/response schemas
    - Authentication requirements
    - Data models
    - Error responses
    """
    spec_urls = [
        f"{repo_url}/blob/main/api/openapi.yaml",
        f"{repo_url}/blob/main/swagger.yaml",
        f"{repo_url}/blob/main/docs/api-spec.yaml"
    ]

    for url in spec_urls:
        spec = fetch_and_parse(url)
        if spec:
            return extract_api_details(spec)
```

### 6. **Service Dependency Graph** (Priority: LOW)

Build a graph of service relationships:

```python
def get_service_dependencies(service_name):
    """
    Return services that:
    - This service depends on
    - Depend on this service
    - Share data models with
    """
    return {
        "depends_on": ["api", "scrooge"],
        "depended_by": ["merchant-dashboard"],
        "shared_models": ["merchant", "invoice"]
    }
```

## Implementation Priority

### Phase 1 (Immediate) ✅

- [x] README fetching (Done)
- [ ] Enhanced prompt to emphasize service context
- [ ] Multi-file documentation fetching

### Phase 2 (Next Sprint)

- [ ] Structured service metadata registry
- [ ] Confluence integration
- [ ] OpenAPI/Swagger parsing

### Phase 3 (Future)

- [ ] Code analysis integration
- [ ] Service dependency graph
- [ ] Real-time service health/metrics

## Quick Win: Service Metadata Registry

**Immediate Action:** Create a simple YAML registry:

```bash
src/services/agents_catalogue/genspec/service_registry/
├── merchant_invoice.yaml
├── api.yaml
├── scrooge.yaml
└── ...
```

Each file contains structured, human-maintained metadata about the service.

**Benefits:**

- Can be implemented TODAY
- Easy to maintain
- Much better than generic READMEs
- Team members can contribute

## Example Enhanced Context Output

Instead of:

```
# merchant_invoice
go-foundation is the boilerplate...
```

We get:

```
## Service: merchant_invoice

**Type:** Microservice (Go)
**Purpose:** Merchant invoice generation and management

### Key APIs:
- POST /v1/invoices - Create invoice
- GET /v1/invoices/{id} - Fetch invoice
- PUT /v1/invoices/{id}/status - Update status

### Integrations:
- **api service**: Fetches merchant data via REST
- **scrooge service**: Calculates pricing via gRPC
- **SQS**: Publishes invoice_created events

### Database:
- invoices (MySQL table)
- invoice_line_items

### Use Cases:
- Generate GST-compliant invoices for merchants
- Track invoice payment status
- Send invoices via email/WhatsApp
```

## Decision

Which approach should we prioritize?

1. **Service Metadata Registry** (easiest, high impact)
2. **Multi-file documentation** (low effort, good improvement)
3. **Confluence integration** (medium effort, high quality)
4. **Code analysis** (high effort, comprehensive)

**Recommendation:** Start with #1 and #2, then add #3.
