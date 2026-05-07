#!/usr/bin/env python3
"""
Test script for ServiceContextManager to verify merchant_invoice context fetching.
"""

import sys
import os
import toml
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent))

from src.services.agents_catalogue.genspec.src.context import ServiceContextManager


def test_service_context_manager():
    """Test the service context manager with merchant_invoice."""
    print("="*80)
    print("Testing ServiceContextManager")
    print("="*80)
    
    # Load configuration
    config_path = Path(__file__).parent / "config.toml"
    print(f"\n1. Loading configuration from: {config_path}")
    
    with open(config_path, 'r') as f:
        config = toml.load(f)
    
    print(f"   ✓ Configuration loaded successfully")
    
    # Initialize service context manager
    print("\n2. Initializing ServiceContextManager")
    context_manager = ServiceContextManager(config)
    
    # Check status
    summary = context_manager.get_service_summary()
    print(f"   ✓ Service context enabled: {summary['enabled']}")
    print(f"   ✓ Total services configured: {summary['total_services']}")
    
    for service in summary['services']:
        print(f"\n   Service: {service['name']}")
        print(f"   - Repository: {service['repo_url']}")
        print(f"   - Cached on disk: {service['cached']}")
        print(f"   - In memory: {service['in_memory']}")
    
    # Fetch all service contexts
    print("\n3. Fetching service contexts...")
    all_contexts = context_manager.get_all_service_contexts()
    
    if all_contexts:
        print(f"   ✓ Successfully fetched service contexts")
        print(f"   ✓ Total context length: {len(all_contexts)} characters")
        
        # Show a preview
        print("\n4. Context Preview:")
        print("-"*80)
        preview_length = min(500, len(all_contexts))
        print(all_contexts[:preview_length])
        if len(all_contexts) > preview_length:
            print(f"\n   ... ({len(all_contexts) - preview_length} more characters)")
        print("-"*80)
        
        # Check cache status after fetching
        print("\n5. Cache Status After Fetch:")
        summary_after = context_manager.get_service_summary()
        for service in summary_after['services']:
            print(f"   - {service['name']}: cached={service['cached']}, in_memory={service['in_memory']}")
        
        return True
    else:
        print("   ✗ Failed to fetch service contexts")
        return False


if __name__ == "__main__":
    try:
        success = test_service_context_manager()
        
        print("\n" + "="*80)
        if success:
            print("✓ TEST PASSED: Service context manager is working correctly!")
        else:
            print("✗ TEST FAILED: Service context manager encountered issues")
        print("="*80)
        
        sys.exit(0 if success else 1)
        
    except Exception as e:
        print(f"\n✗ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

