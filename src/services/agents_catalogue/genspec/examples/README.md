# Tech-SpecGen Examples

This directory contains example files to demonstrate how to use Tech-SpecGen.

## Example Files

### Problem Statement

`example_problem.txt` - A sample problem statement that describes the challenge to be solved.

### Architecture Diagram

`example_architecture.png` - A sample architecture diagram in PNG format.

### PRD Document

`example_prd.md` - A sample Product Requirements Document in Markdown format.

## How to Use These Examples

### With Interactive CLI

Run the interactive CLI and reference these files when prompted:

```bash
python -m src.interactive_cli
```

### With Command Line

Use these examples directly with the command line interface:

```bash
python -m src.main \
  --project-name "Example Project" \
  --problem-statement "examples/example_problem.txt" \
  --architecture-diagram "examples/example_architecture.png" \
  --prd "examples/example_prd.md" \
  --output-dir "output" \
  --output-format "both"
```

## Creating Your Own Examples

When creating your own files for use with Tech-SpecGen:

1. **Problem Statement**: Create a text file that clearly describes the problem to be solved
2. **Architecture Diagram**: Create a PNG or JPG image of your current architecture
3. **PRD**: Create a Markdown document with your product requirements

For best results, include as much detail as possible in each document.
