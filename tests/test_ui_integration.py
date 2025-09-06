#!/usr/bin/env python3
"""
Quick test to verify UI integration works correctly
"""

import os
import sys
import json

# Set environment variables
os.environ['FORCE_GRANITE'] = 'true'
os.environ['DUAL_MODEL_ENABLED'] = 'false'
os.environ['RULES_MODE_ENABLED'] = 'true'

# Import required modules
from utils.granite_client import GraniteClient

def test_granite_client():
    """Test if GraniteClient works correctly"""
    print("Testing GraniteClient...")
    
    try:
        client = GraniteClient()
        print(f"✅ Client initialized: {client.model_name}")
        
        # Test system message call
        system_msg = "You are a helpful assistant. Respond with a JSON object containing a 'status' field."
        user_msg = "Test message - please respond with status: ok"
        
        response = client.call_api_with_system_message(
            system_msg,
            user_msg,
            temperature=0.1,
            max_tokens=100
        )
        
        print(f"✅ Response received: {response[:100]}...")
        
        # Test if it's valid JSON
        try:
            json.loads(response)
            print("✅ Valid JSON response")
        except:
            print("⚠️ Response is not JSON (expected for general text)")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_rule_compliance_evaluator():
    """Test if RuleComplianceEvaluator works"""
    print("\nTesting RuleComplianceEvaluator...")
    
    try:
        from nodes.rule_compliance_evaluator import RuleComplianceEvaluator
        
        # Create simple state
        
        RuleComplianceEvaluator()
        print("✅ RuleComplianceEvaluator initialized")
        
        # Note: We won't run process() as it requires full state setup
        # Just verify it can be instantiated
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    print("="*60)
    print("UI Integration Test")
    print("="*60)
    
    results = []
    
    # Test GraniteClient
    results.append(test_granite_client())
    
    # Test RuleComplianceEvaluator
    results.append(test_rule_compliance_evaluator())
    
    print("\n" + "="*60)
    if all(results):
        print("✅ All tests passed!")
    else:
        print("❌ Some tests failed")
        sys.exit(1)

if __name__ == "__main__":
    main()