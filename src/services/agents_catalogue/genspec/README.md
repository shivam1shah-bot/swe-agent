# GenSpec - Step-by-Step Guide

GenSpec is a comprehensive technical specification generator that analyzes various inputs (problem statements, PRDs, architecture diagrams) to produce standardized technical documentation using AWS Bedrock and Claude.

## Features

- **Multi-source Analysis**: Automatically ingests and analyzes content from problem statements, PRDs, architecture diagrams (both image and text formats) and database specifications to generate context-aware specs
- **Standardized Output**: Generates consistent technical specifications following best practices
- **Customizable Templates**: Adapts to different specification formats and organizational needs
- **AWS Bedrock Integration**: Leverages Claude's capabilities for high-quality content generation
- **Image-based Current Architecture Support**: Accepts PNG/JPG diagrams, preserves them as-is in the output, and also allows text-based architecture descriptions for full flexibility.
- **Interactive CLI**: Guided interface for collecting all necessary information for comprehensive specifications
- **Database Evalaution**: Comprehensively compares different databases based on your requirements and intelligently recommends the one best suited
- **DB Cost Analysis**: Evaluates costs across AWS, Google Cloud, and Azure based on your configuration (instances, vCPUs, memory) to optimize your infrastructure budget.

## Features Under Development

We're actively working on enhancing GenSpec with the following capabilities:

- **API Endpoint Extraction**: Automatically extract API specifications from documentation websites
- **Codebase Analysis**: Extract API specifications directly from source code
- **Blog Analysis**: Extract technical insights from blog posts and technical articles

## Getting Started

### Prerequisites

- Python 3.8+
- AWS account with Bedrock access
- AWS credentials with appropriate permissions

### Installation

1. Clone the repository:

   ```bash
   git clone https://github.com/yourusername/GenSpec.git
   cd GenSpec
   ```

2. Install dependencies:

   ```bash
   pip3 install -r requirements.txt
   ```

3. Configure AWS credentials:
   ```bash
   cp config.example.yaml config.yaml
   ```
4. Edit `config.yaml` with your AWS credentials:

   ```yaml
   aws:
     access_key_id: YOUR_ACCESS_KEY
     secret_access_key: YOUR_SECRET_KEY
     session_token: YOUR_SESSION_TOKEN

   paths:
     architecture_images: assets/architecture_images
     output: output
   ```

   Alternatively, you can set environment variables:

   ```bash
   export AWS_ACCESS_KEY_ID=YOUR_ACCESS_KEY
   export AWS_SECRET_ACCESS_KEY=YOUR_SECRET_KEY
   export AWS_SESSION_TOKEN=YOUR_SESSION_TOKEN
   ```

## AWS Bedrock Keys :

Refer to this docs for obtaining the AWS BEDROCK KEYS : https://docs.google.com/document/d/1265_wjKAyc-TN3mitzRbw_kR_3ZMga9riXqi8KWBw4w/edit?tab=t.0#heading=h.wgfw6j9rvy2m

## Step-by-Step Usage Guide

### Running the Interactive CLI

1. Start the interactive CLI:

   ```bash
   python3 -m src.interactive_cli
   ```

2. Enter your project name when prompted:

   ```
   What is the name of your project? MyProject
   ```

3. Provide a problem statement either:
   - Directly in the terminal (type 'END' on a new line when finished)
   - Or specify a file path (e.g., `problem_statements/my_problem.txt`)

4. Add an architecture diagram:
   - Choose from: Image file (PNG/JPG), Mermaid diagram code, or Text description
   - For image files, provide the path (e.g., `architecture/current_diagram.png`)
   - For Mermaid diagrams, enter the code directly (type 'END' when finished)
   - For text descriptions, describe your architecture in words (type 'END' when finished)

5. Add a PRD document (optional):
   - Provide a file path (e.g., `documents/prd.md`)
   - Or enter the PRD content directly

6. Specify a codebase path for analysis (optional):
   - Provide the path to your codebase (e.g., `src/myproject/`)

7. Configure additional parameters:
   - Database evaluation options
   - Performance requirements
   - Output format preferences

8. Confirm your inputs and generate the specification:
   - Review the summary of your inputs
   - Confirm to start the generation process

9. Find your generated specification:
   - The output will be saved to `output/[project_name]/specification.md`
   - If HTML output was selected, also at `output/[project_name]/specification.html`

### Example Workflow

```bash
# Clone and set up the project
git clone https://github.com/yourusername/GenSpec.git
cd GenSpec
pip install -r requirements.txt
cp config.example.yaml config.yaml
# Edit config.yaml with your AWS credentials

# Run the interactive CLI
python -m src.interactive_cli

# Follow the prompts to enter:
# - Project name: "AUTOPAY"
# - Problem statement: Describe the technical challenges
# - Architecture diagram: Provide a PNG file at "diagrams/current_arch.png"
# - PRD document: Provide at "docs/product_requirements.md"
# - Additional parameters as needed

# Generated specification will be available at:
# output/AUTOPAY/specification.md
```

### File Locations

- **Problem statements**: Can be stored anywhere, just provide the path
- **Architecture diagrams**: Recommended to store in `architecture/` directory
- **PRD documents**: Can be stored anywhere, just provide the path
- **Output files**: Generated in `output/[project_name]/`

## Architecture

Tech-SpecGen follows a modular architecture:

1. **Input Processing**: Parsers for different input types (PRDs, diagrams, code)
2. **Specification Generation**: Core logic for generating specifications
3. **Formatting**: Markdown formatter for output generation

## All flowcharts are being generated as mermaid code, to the render the same use :

https://mermaid.live/edit#pako:eNpVjcFugzAQRH_F2lMrkYiYEIwPlRrS5hKpPfRUyMEKC0YNNjJGaQr8ew1R1XZOO5o3sz2cdI7AoTjry0kKY8nbLlPE6TFNpKlaW4v2SBaLh2GPltRa4XUg27u9Jq3UTVOp8v7GbyeIJP1hwpBYWamP8RYlc_9F4UB26UE0VjfHv8nbRQ_kKa1epZv_n0iDrvWcFoIXYnEShiTCzAh4UJoqB25Nhx7UaGoxWeinNAMrscYMuDtzLER3thlkanS1Rqh3reufptFdKcHNn1vnuiYXFneVKI34RVDlaBLdKQt8FcwTwHv4BE7jaBmHjLIVXYWMBWzjwRV4GCzXcRxHdB3ENGCRvx49-Jq_-ksWhb4T3fhR5NOQjt-1bXck

## The final tech spec is generated in both .md and .html format (you can directly upload your .md file to google docs)
