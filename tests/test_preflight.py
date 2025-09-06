#!/usr/bin/env python3
"""
Test script for the preflight check node.

This script tests the preflight check functionality independently
to verify model endpoint connectivity.
"""

import sys
import os
import json
from datetime import datetime

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from nodes.preflight_check import preflight_check

def test_preflight_check():
    """Test the preflight check node."""
    print("=" * 60)
    print("TESTING PREFLIGHT CHECK NODE")
    print("=" * 60)
    
    # Create a minimal state for testing
    test_state = {
        'target_document_path': '/test/document.pdf',
        'reference_document_path': '/test/reference.pdf',
        'processing_errors': [],
        'preflight_results': None
    }
    
    try:
        # Run the preflight check
        print("Running preflight check...")
        result = preflight_check(test_state)
        
        print("\n" + "=" * 60)
        print("PREFLIGHT CHECK RESULTS")
        print("=" * 60)
        
        # Print the results
        if 'preflight_results' in result:
            preflight_data = result['preflight_results']
            
            print(f"Overall Success: {preflight_data.get('overall_success', 'Unknown')}")
            print(f"Total Response Time: {preflight_data.get('total_response_time', 0):.2f}s")
            print(f"Required Models: {', '.join(preflight_data.get('required_models', []))}")
            print(f"Successful Models: {', '.join(preflight_data.get('successful_models', []))}")
            print(f"Failed Models: {', '.join(preflight_data.get('failed_models', []))}")
            
            print("\nDetailed Test Results:")
            for test_result in preflight_data.get('test_results', []):
                print(f"  {test_result['name']}: {test_result['status']} "
                      f"({test_result['response_time_ms']}ms)")
                if test_result.get('error'):
                    print(f"    Error: {test_result['error']}")
                if test_result.get('response_preview'):
                    print(f"    Response: {test_result['response_preview']}")
            
            print("\nConfiguration Used:")
            config = preflight_data.get('config_used', {})
            print(f"  Dual Model Enabled: {config.get('dual_model_enabled', 'Unknown')}")
            print(f"  Use Tuned Model: {config.get('use_tuned_model', 'Unknown')}")
            print(f"  Primary Model: {config.get('primary_model', 'Unknown')}")
            
        if 'processing_errors' in result:
            errors = result['processing_errors']
            if errors:
                print(f"\nProcessing Errors: {len(errors)}")
                for error in errors:
                    print(f"  - {error}")
        
        # Save results to file for inspection (under data/output/preflight)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        app_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        base_dir = os.path.join(app_root, "data", "output", "preflight")
        os.makedirs(base_dir, exist_ok=True)
        output_file = os.path.join(base_dir, f"preflight_test_results_{timestamp}.json")
        
        with open(output_file, 'w') as f:
            json.dump(result, f, indent=2, default=str)
        
        print(f"\nResults saved to: {output_file}")
        
        return preflight_data.get('overall_success', False) if 'preflight_results' in result else False
        
    except Exception as e:
        print(f"\nERROR running preflight check: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("Starting preflight check test...")
    
    success = test_preflight_check()
    
    print("\n" + "=" * 60)
    if success:
        print("✅ PREFLIGHT CHECK PASSED - All models accessible")
        print("You can proceed with running the main workflow.")
        sys.exit(0)
    else:
        print("❌ PREFLIGHT CHECK FAILED - Model connectivity issues")
        print("Check your model configurations and endpoints.")
        sys.exit(1) 