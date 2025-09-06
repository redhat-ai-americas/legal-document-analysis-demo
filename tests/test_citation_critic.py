#!/usr/bin/env python3
"""
Test script for the Citation Critic Agent
Tests validation logic and conditional rerun decisions
"""

import os
import sys
from typing import Dict, Any

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from nodes.citation_critic import citation_critic_node, should_rerun_citations
from utils.citation_tracker import citation_tracker, CitationType

def create_test_state_with_issues() -> Dict[str, Any]:
    """Create a test state with citation issues."""
    
    # Clear citation tracker
    citation_tracker.citations = {}
    citation_tracker.next_citation_id = 1
    
    # Create some test citations with issues
    
    # Good citation with page anchor
    good_citation = citation_tracker.create_citation(
        source_text="This is a well-referenced clause from the contract.",
        citation_type=CitationType.DIRECT_QUOTE,
        page_number=5,
        section_name="Terms",
        confidence=0.85
    )
    
    # Bad citation with unknown location
    bad_citation1 = citation_tracker.create_citation(
        source_text="Some text without proper location.",
        citation_type=CitationType.INFERENCE,
        page_number=None,
        section_name=None,
        confidence=0.3
    )
    
    # Bad citation with low confidence
    bad_citation2 = citation_tracker.create_citation(
        source_text="Uncertain reference.",
        citation_type=CitationType.PARAPHRASE,
        page_number=2,
        section_name="Liability",
        confidence=0.2
    )
    
    # Create test state
    state = {
        'questionnaire_responses': {
            'part_1_document_information': {
                'questions': [
                    {
                        'id': 'contract_start_date',
                        'answer': 'DETERMINISTIC_FIELD',
                        'confidence': 100,
                        'citations': []  # Deterministic fields don't need citations
                    },
                    {
                        'id': 'limitation_of_liability',
                        'answer': 'Liability is limited to direct damages only.',
                        'confidence': 0.85,
                        'citations': [good_citation.citation_id]
                    },
                    {
                        'id': 'indemnity',
                        'answer': 'Mutual indemnification clause present.',
                        'confidence': 0.3,
                        'citations': [bad_citation1.citation_id, bad_citation2.citation_id]
                    },
                    {
                        'id': 'ip_rights',
                        'answer': 'All IP remains with original owner.',
                        'confidence': 0.45,
                        'citations': []  # Empty citations for non-deterministic field
                    }
                ]
            }
        },
        'compliance_summary': {
            'rules_with_citations': [
                {
                    'rule_id': 'RULE_001',
                    'citations': [
                        {
                            'location': 'Unknown location',
                            'source_text': 'Some compliance text'
                        }
                    ]
                },
                {
                    'rule_id': 'RULE_002',
                    'citations': [
                        {
                            'location': '[[page=7]]',
                            'source_text': 'Well-anchored compliance text',
                            'page_anchor': '[[page=7]]'
                        }
                    ]
                }
            ]
        },
        'citation_critic_attempts': 0
    }
    
    return state


def create_test_state_good() -> Dict[str, Any]:
    """Create a test state with good citations."""
    
    # Clear citation tracker
    citation_tracker.citations = {}
    citation_tracker.next_citation_id = 1
    
    # Create good citations
    citation1 = citation_tracker.create_citation(
        source_text="Clear termination clause with 30 days notice.",
        citation_type=CitationType.DIRECT_QUOTE,
        page_number=3,
        section_name="Termination",
        confidence=0.95
    )
    
    citation2 = citation_tracker.create_citation(
        source_text="Liability limited to fees paid in last 12 months.",
        citation_type=CitationType.DIRECT_QUOTE,
        page_number=8,
        section_name="Limitation of Liability",
        confidence=0.88
    )
    
    state = {
        'questionnaire_responses': {
            'part_2_key_clause_analysis': {
                'questions': [
                    {
                        'id': 'termination',
                        'answer': '30 days notice required',
                        'confidence': 0.95,
                        'citations': [citation1.citation_id]
                    },
                    {
                        'id': 'liability_cap',
                        'answer': 'Limited to 12 months fees',
                        'confidence': 0.88,
                        'citations': [citation2.citation_id]
                    }
                ]
            }
        },
        'citation_critic_attempts': 0
    }
    
    return state


def test_critic_with_issues():
    """Test critic with citation issues."""
    print("\n" + "="*60)
    print("TEST 1: State with Citation Issues")
    print("="*60)
    
    state = create_test_state_with_issues()
    
    # Set environment variables for testing with stricter thresholds
    os.environ['CITATION_MIN_CONFIDENCE'] = '0.6'
    os.environ['CITATION_REQUIRE_ANCHORS'] = 'true'
    os.environ['CITATION_MAX_UNKNOWN'] = '1'  # Stricter: only 1 unknown allowed
    os.environ['CITATION_MAX_RERUNS'] = '3'
    
    # Run critic
    result = citation_critic_node(state)
    
    # Check results
    validation = result['citation_validation_results']
    
    print("\nValidation Results:")
    print(f"  Total citations: {validation['total_citations']}")
    print(f"  Empty citations: {validation['empty_citations']}")
    print(f"  Missing page anchors: {validation['missing_page_anchors']}")
    print(f"  Unknown locations: {validation['unknown_locations']}")
    print(f"  Low confidence: {validation['low_confidence']}")
    print(f"  Severity: {validation['severity']}")
    print(f"  Validation passed: {validation['validation_passed']}")
    print(f"  Needs rerun: {result['needs_citation_rerun']}")
    
    print(f"\nIssues found ({len(validation['issues'])}):")
    for issue in validation['issues'][:5]:  # Show first 5 issues
        print(f"  [{issue['severity']}] {issue['type']}: {issue['message']}")
    
    print(f"\nRecommendations ({len(validation['recommendations'])}):")
    for rec in validation['recommendations']:
        print(f"  [{rec['priority']}] {rec['message']}")
    
    # Test conditional edge
    state.update(result)
    decision = should_rerun_citations(state)
    print(f"\nConditional edge decision: {decision}")
    
    assert result['needs_citation_rerun'], "Should need rerun with issues"
    assert decision == "rerun_classification", "Should decide to rerun"
    
    print("\n✅ Test 1 PASSED: Correctly identified issues and triggered rerun")


def test_critic_with_good_citations():
    """Test critic with good citations."""
    print("\n" + "="*60)
    print("TEST 2: State with Good Citations")
    print("="*60)
    
    state = create_test_state_good()
    
    # Run critic
    result = citation_critic_node(state)
    
    # Check results
    validation = result['citation_validation_results']
    
    print("\nValidation Results:")
    print(f"  Total citations: {validation['total_citations']}")
    print(f"  Empty citations: {validation['empty_citations']}")
    print(f"  Missing page anchors: {validation['missing_page_anchors']}")
    print(f"  Unknown locations: {validation['unknown_locations']}")
    print(f"  Severity: {validation['severity']}")
    print(f"  Validation passed: {validation['validation_passed']}")
    print(f"  Needs rerun: {result['needs_citation_rerun']}")
    
    # Test conditional edge
    state.update(result)
    decision = should_rerun_citations(state)
    print(f"\nConditional edge decision: {decision}")
    
    assert not result['needs_citation_rerun'], "Should not need rerun"
    assert decision == "continue", "Should continue to next node"
    
    print("\n✅ Test 2 PASSED: Good citations passed validation")


def test_max_reruns():
    """Test that reruns stop after max attempts."""
    print("\n" + "="*60)
    print("TEST 3: Max Rerun Limit")
    print("="*60)
    
    state = create_test_state_with_issues()
    state['citation_critic_attempts'] = 2  # Already attempted twice
    
    os.environ['CITATION_MAX_RERUNS'] = '3'
    
    # Run critic
    result = citation_critic_node(state)
    
    print(f"\nAttempt number: {result['citation_critic_attempts']}")
    print(f"Needs rerun: {result['needs_citation_rerun']}")
    print(f"Validation passed: {result['citation_validation_results']['validation_passed']}")
    
    # Should be on attempt 3 now, which is the max
    assert result['citation_critic_attempts'] == 3, "Should be on attempt 3"
    assert not result['needs_citation_rerun'], "Should not rerun after max attempts"
    
    # Test conditional edge
    state.update(result)
    decision = should_rerun_citations(state)
    print(f"Conditional edge decision: {decision}")
    
    assert decision == "continue", "Should continue despite issues (max reruns reached)"
    
    print("\n✅ Test 3 PASSED: Reruns stop at max limit")


def main():
    """Run all tests."""
    print("\nTesting Citation Critic Agent")
    print("==============================")
    
    try:
        test_critic_with_issues()
        test_critic_with_good_citations()
        test_max_reruns()
        
        print("\n" + "="*60)
        print("ALL TESTS PASSED! 🎉")
        print("="*60)
        print("\nThe Citation Critic Agent is working correctly:")
        print("✓ Detects citation issues (missing anchors, low confidence, etc.)")
        print("✓ Triggers conditional reruns when issues are severe")
        print("✓ Passes validation for good citations")
        print("✓ Respects maximum rerun limit")
        print("✓ Integrates with LangGraph conditional edges")
        
        return 0
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        return 1
    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())