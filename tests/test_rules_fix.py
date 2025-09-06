#!/usr/bin/env python
"""Test script to verify rules processing conditional behavior"""

import os
import sys
from workflows.graph_builder import build_graph

def test_rules_disabled():
    """Test that rules are skipped when RULES_MODE_ENABLED=false"""
    print("\n" + "="*60)
    print("TEST 1: Rules DISABLED (RULES_MODE_ENABLED=false)")
    print("="*60)
    
    # Set rules to disabled
    os.environ['RULES_MODE_ENABLED'] = 'false'
    
    # Build the graph
    app = build_graph()
    
    # Check the graph structure
    print("\nGraph nodes:")
    for node in app.nodes:
        print(f"  - {node}")
    
    # Check if rules nodes are in the graph
    has_rules = 'rules_loader' in app.nodes or 'rule_compliance_checker' in app.nodes
    
    if has_rules:
        print("\n❌ FAIL: Rules nodes found in graph when RULES_MODE_ENABLED=false")
        return False
    else:
        print("\n✅ PASS: Rules nodes correctly excluded when disabled")
        return True

def test_rules_enabled():
    """Test that rules are included when RULES_MODE_ENABLED=true"""
    print("\n" + "="*60)
    print("TEST 2: Rules ENABLED (RULES_MODE_ENABLED=true)")
    print("="*60)
    
    # Set rules to enabled
    os.environ['RULES_MODE_ENABLED'] = 'true'
    os.environ['RULES_PATH'] = '/dummy/path/rules.csv'  # Set a dummy path
    
    # Build the graph
    app = build_graph()
    
    # Check the graph structure
    print("\nGraph nodes:")
    for node in app.nodes:
        print(f"  - {node}")
    
    # Check if rules nodes are in the graph
    has_rules = 'rules_loader' in app.nodes and 'rule_compliance_checker' in app.nodes
    
    if has_rules:
        print("\n✅ PASS: Rules nodes correctly included when enabled")
        return True
    else:
        print("\n❌ FAIL: Rules nodes missing when RULES_MODE_ENABLED=true")
        return False

def test_rules_enabled_no_path():
    """Test that rules can be enabled even without initial path (path can come from state)"""
    print("\n" + "="*60)
    print("TEST 3: Rules ENABLED without initial path")
    print("="*60)
    
    # Set rules to enabled but no path
    os.environ['RULES_MODE_ENABLED'] = 'true'
    os.environ.pop('RULES_PATH', None)  # Remove RULES_PATH if it exists
    
    # Build the graph
    app = build_graph()
    
    # Check the graph structure
    print("\nGraph nodes:")
    for node in app.nodes:
        print(f"  - {node}")
    
    # Check if rules nodes are in the graph (they should be added, routing will decide at runtime)
    has_rules = 'rules_loader' in app.nodes and 'rule_compliance_checker' in app.nodes
    
    if has_rules:
        print("\n✅ PASS: Rules nodes included, routing will decide at runtime based on state")
        return True
    else:
        print("\n❌ FAIL: Rules nodes should be included when enabled")
        return False

def main():
    """Run all tests"""
    print("\nTesting Rules Processing Conditional Fix")
    print("=========================================")
    
    results = []
    
    # Run tests
    results.append(test_rules_disabled())
    results.append(test_rules_enabled())
    results.append(test_rules_enabled_no_path())
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    passed = sum(results)
    total = len(results)
    
    if passed == total:
        print(f"✅ ALL TESTS PASSED ({passed}/{total})")
        return 0
    else:
        print(f"❌ SOME TESTS FAILED ({passed}/{total} passed)")
        return 1

if __name__ == "__main__":
    sys.exit(main())