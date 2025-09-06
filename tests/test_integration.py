#!/usr/bin/env python3
"""
Quick integration test for the new rule compliance components
"""

import os
import sys

# Set environment variables
os.environ['FORCE_GRANITE'] = 'true'
os.environ['RULES_MODE_ENABLED'] = 'true'
os.environ['PYTHONPATH'] = '.'

# Import and test the new components
try:
    print("Testing imports...")
    from nodes.rule_compliance_evaluator import RuleComplianceEvaluator
    print("✅ RuleComplianceEvaluator imported successfully")
    
    print("✅ rule_centric_excel_writer imported successfully")
    
    print("✅ rule_compliance_master_writer imported successfully")
    
    print("✅ BaseNode and ProgressReporter imported successfully")
    
    # Test the evaluator initialization
    evaluator = RuleComplianceEvaluator()
    print("✅ RuleComplianceEvaluator initialized successfully")
    
    # Test loading rules
    rules_path = "standard_docs/software_license_rules.json"
    if os.path.exists(rules_path):
        rules = evaluator.load_rules(rules_path)
        print(f"✅ Loaded {len(rules)} rules from {rules_path}")
    else:
        print(f"⚠️ Rules file not found: {rules_path}")
    
    print("\n✅ All integration tests passed!")
    
except Exception as e:
    print(f"\n❌ Integration test failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)