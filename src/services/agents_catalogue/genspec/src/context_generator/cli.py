"""
Command-line interface for Context Generator.
"""

import os
import sys
import argparse
import logging
from typing import Dict, List, Any, Optional
import json

from .config import Config
from .analyzer import CodebaseAnalyzer
from .generator import DocumentationGenerator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    """
    Parse command-line arguments.
    
    Returns:
        Parsed arguments
    """
    parser = argparse.ArgumentParser(
        description='Context Generator - Analyze codebases and generate comprehensive documentation'
    )
    
    parser.add_argument(
        'codebase_path',
        help='Path to the codebase to analyze'
    )
    
    parser.add_argument(
        '-o', '--output-dir',
        default='docs',
        help='Directory to output generated documentation (default: docs)'
    )
    
    parser.add_argument(
        '-c', '--config',
        help='Path to configuration file'
    )
    
    parser.add_argument(
        '-i', '--ignore',
        action='append',
        help='Glob patterns to ignore (can be specified multiple times)'
    )
    
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Enable verbose output'
    )
    
    parser.add_argument(
        '--import-prompts',
        help='URL to import prompts from'
    )
    
    return parser.parse_args()


def main() -> int:
    """
    Main entry point for the CLI.
    
    Returns:
        Exit code
    """
    args = parse_args()
    
    # Set log level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Load configuration
    config = Config(args.config)
    try:
        config.load()
    except Exception as e:
        logger.error(f"Error loading configuration: {str(e)}")
        return 1
    
    # Add import if specified
    if args.import_prompts:
        if "import" not in config.config_data:
            config.config_data["import"] = []
        
        config.config_data["import"].append({
            "type": "url",
            "url": args.import_prompts
        })
        
        # Process the new import
        config._process_imports([{"type": "url", "url": args.import_prompts}])
    
    # Verify codebase path exists
    if not os.path.exists(args.codebase_path):
        logger.error(f"Codebase path does not exist: {args.codebase_path}")
        return 1
    
    # Analyze codebase
    logger.info(f"Analyzing codebase: {args.codebase_path}")
    analyzer = CodebaseAnalyzer(args.codebase_path, args.ignore)
    
    try:
        analysis_results = analyzer.analyze()
        logger.info("Analysis completed successfully")
    except Exception as e:
        logger.error(f"Error analyzing codebase: {str(e)}")
        return 1
    
    # Generate documentation
    logger.info(f"Generating documentation in: {args.output_dir}")
    generator = DocumentationGenerator(analysis_results, args.output_dir)
    
    try:
        generated_files = generator.generate_all()
        logger.info(f"Generated {len(generated_files)} documentation files")
    except Exception as e:
        logger.error(f"Error generating documentation: {str(e)}")
        return 1
    
    # Output summary
    print("\nContext Generator Summary:")
    print(f"- Analyzed codebase: {args.codebase_path}")
    print(f"- Generated documentation in: {args.output_dir}")
    print(f"- Found {len(analysis_results.get('apis', []))} API endpoints")
    print(f"- Found {len(analysis_results.get('jobs', []))} jobs/tasks")
    print(f"- Found {len(analysis_results.get('failure_points', []))} potential failure points")
    print(f"- Found {len(analysis_results.get('retry_mechanisms', []))} retry mechanisms")
    print(f"- Found {len(analysis_results.get('idempotency_mechanisms', []))} idempotency mechanisms")
    print("\nDocumentation files:")
    for file_name in sorted(generated_files.keys()):
        print(f"- {os.path.join(args.output_dir, file_name)}")
    
    return 0


if __name__ == '__main__':
    sys.exit(main()) 