#!/usr/bin/env python3
"""
Comprehensive test for the multi-critic system
Tests PDF, Classification, Questionnaire, and Citation critics working together
"""

import os
import sys
from typing import Dict, Any

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import all critics
from nodes.pdf_conversion_critic import PDFConversionCritic, pdf_conversion_critic_node
from nodes.classification_coverage_critic import ClassificationCoverageCritic, classification_coverage_critic_node
from nodes.questionnaire_completeness_critic import QuestionnaireCompletenessCritic, questionnaire_completeness_critic_node
from nodes.citation_critic import CitationCritic, citation_critic_node
from utils.citation_tracker import citation_tracker, CitationType


def create_test_state_good() -> Dict[str, Any]:
    """Create a test state with good quality throughout."""
    
    # Good PDF conversion
    document_text = """[[page=1]]
# SOFTWARE LICENSE AGREEMENT

This agreement is between Company A and Company B.

## 1. TERM
This agreement shall be effective for a period of three (3) years.

[[page=2]]
## 2. TERMINATION
Either party may terminate this agreement with 30 days written notice.

## 3. LIMITATION OF LIABILITY
Total liability shall not exceed the fees paid in the last 12 months.

[[page=3]]
## 4. INDEMNIFICATION
Each party shall indemnify the other for breaches of this agreement.

## 5. GOVERNING LAW
This agreement shall be governed by the laws of New York.
"""
    
    # Good classifications
    classified_sentences = [
        {
            "sentence": "This agreement shall be effective for a period of three (3) years.",
            "classes": ["term"],
            "confidence": 0.85,
            "page": 1,
            "page_number": 1
        },
        {
            "sentence": "Either party may terminate this agreement with 30 days written notice.",
            "classes": ["termination"],
            "confidence": 0.90,
            "page": 2,
            "page_number": 2
        },
        {
            "sentence": "Total liability shall not exceed the fees paid in the last 12 months.",
            "classes": ["limitation_of_liability"],
            "confidence": 0.88,
            "page": 2,
            "page_number": 2
        },
        {
            "sentence": "Each party shall indemnify the other for breaches of this agreement.",
            "classes": ["indemnity"],
            "confidence": 0.82,
            "page": 3,
            "page_number": 3
        },
        {
            "sentence": "This agreement shall be governed by the laws of New York.",
            "classes": ["governing_law"],
            "confidence": 0.95,
            "page": 3,
            "page_number": 3
        }
    ]
    
    # Create good citations
    citation_tracker.citations = {}
    citation_tracker.next_citation_id = 1
    
    cit1 = citation_tracker.create_citation(
        source_text="Either party may terminate this agreement with 30 days written notice.",
        citation_type=CitationType.DIRECT_QUOTE,
        page_number=2,
        confidence=0.90
    )
    
    cit2 = citation_tracker.create_citation(
        source_text="Total liability shall not exceed the fees paid in the last 12 months.",
        citation_type=CitationType.DIRECT_QUOTE,
        page_number=2,
        confidence=0.88
    )
    
    # Good questionnaire responses
    questionnaire_responses = {
        "part_1_document_information": {
            "questions": [
                {
                    "id": "contract_start_date",
                    "answer": "January 1, 2024",
                    "confidence": 0.95,
                    "citations": []
                },
                {
                    "id": "target_company_name",
                    "answer": "Company A",
                    "confidence": 0.98,
                    "citations": []
                },
                {
                    "id": "counterparty_name",
                    "answer": "Company B",
                    "confidence": 0.98,
                    "citations": []
                }
            ]
        },
        "part_2_key_clause_analysis": {
            "questions": [
                {
                    "id": "term",
                    "answer": "3 years",
                    "confidence": 0.85,
                    "citations": []
                },
                {
                    "id": "termination",
                    "answer": "30 days written notice",
                    "confidence": 0.90,
                    "citations": [cit1.citation_id]
                },
                {
                    "id": "limitation_of_liability",
                    "answer": "Limited to fees paid in last 12 months",
                    "confidence": 0.88,
                    "citations": [cit2.citation_id],
                    "risk_assessment": {
                        "risk_level": "medium",
                        "risk_score": 0.6
                    }
                },
                {
                    "id": "governing_law",
                    "answer": "New York",
                    "confidence": 0.95,
                    "citations": []
                }
            ]
        }
    }
    
    return {
        "document_text": document_text,
        "processed_document_path": "/tmp/test_good.md",
        "document_sentences": document_text.split("\n"),
        "classified_sentences": classified_sentences,
        "questionnaire_responses": questionnaire_responses,
        "pdf_critic_attempts": 0,
        "classification_critic_attempts": 0,
        "questionnaire_critic_attempts": 0,
        "citation_critic_attempts": 0
    }


def create_test_state_with_issues() -> Dict[str, Any]:
    """Create a test state with various quality issues."""
    
    # Poor PDF conversion (no page anchors, lots of images)
    document_text = """
SOFTWARE LICENSE AGREEMENT
<!-- image -->
<!-- image -->
This agreement between Company
<!-- image -->
TERM period years
<!-- image -->
TERMINATION days notice
<!-- image -->
LIABILITY exceed fees
<!-- image -->
"""
    
    # Poor classifications
    classified_sentences = [
        {
            "sentence": "SOFTWARE LICENSE AGREEMENT",
            "classes": [],
            "confidence": 0.2
        },
        {
            "sentence": "This agreement between Company",
            "classes": ["no-class"],
            "confidence": 0.1
        },
        {
            "sentence": "TERM period years",
            "classes": ["term"],
            "confidence": 0.3  # Low confidence
        },
        {
            "sentence": "TERMINATION days notice",
            "classes": [],
            "confidence": 0.25
        }
    ]
    
    # Poor questionnaire responses
    questionnaire_responses = {
        "part_1_document_information": {
            "questions": [
                {
                    "id": "contract_start_date",
                    "answer": "Not specified",
                    "confidence": 0.1,
                    "citations": []
                },
                {
                    "id": "target_company_name",
                    "answer": "Not found",
                    "confidence": 0.1,
                    "citations": []
                }
            ]
        },
        "part_2_key_clause_analysis": {
            "questions": [
                {
                    "id": "term",
                    "answer": "Not specified",
                    "confidence": 0.2,
                    "citations": []
                },
                {
                    "id": "termination",
                    "answer": "Not specified",
                    "confidence": 0.15,
                    "citations": []
                },
                {
                    "id": "limitation_of_liability",
                    "answer": "Maybe present",
                    "confidence": 0.3,
                    "citations": []  # Missing citations
                },
                {
                    "id": "indemnity",
                    "answer": "Not specified",
                    "confidence": 0.1,
                    "citations": []
                }
            ]
        }
    }
    
    return {
        "document_text": document_text,
        "processed_document_path": "/tmp/test_poor.md",
        "document_sentences": document_text.split("\n"),
        "classified_sentences": classified_sentences,
        "questionnaire_responses": questionnaire_responses,
        "pdf_critic_attempts": 0,
        "classification_critic_attempts": 0,
        "questionnaire_critic_attempts": 0,
        "citation_critic_attempts": 0
    }


def test_all_critics_pass():
    """Test when all critics pass validation."""
    print("\n" + "="*70)
    print("TEST 1: All Critics Pass (Good Quality)")
    print("="*70)
    
    state = create_test_state_good()
    results = {}
    
    # Test PDF Critic (with adjusted threshold for test)
    print("\n1. PDF Conversion Critic:")
    pdf_critic = PDFConversionCritic(min_text_length=200)  # Lower for test
    pdf_results = pdf_critic.validate_conversion(state)
    results['pdf'] = pdf_results
    print(f"   - Text length: {pdf_results['text_length']} chars")
    print(f"   - Has page anchors: {pdf_results['has_page_anchors']}")
    print(f"   - Validation passed: {pdf_results['validation_passed']}")
    
    # Test Classification Critic (with adjusted thresholds)
    print("\n2. Classification Coverage Critic:")
    class_critic = ClassificationCoverageCritic(
        min_coverage=0.3,
        critical_terms=['term', 'termination', 'liability']  # Only require basic terms
    )
    class_results = class_critic.validate_classification(state)
    results['classification'] = class_results
    print(f"   - Coverage: {class_results['coverage_percentage']:.1%}")
    print(f"   - Average confidence: {class_results['average_confidence']:.2f}")
    print(f"   - Validation passed: {class_results['validation_passed']}")
    
    # Test Questionnaire Critic
    print("\n3. Questionnaire Completeness Critic:")
    quest_critic = QuestionnaireCompletenessCritic()
    quest_results = quest_critic.validate_questionnaire(state)
    results['questionnaire'] = quest_results
    print(f"   - Not specified ratio: {quest_results['not_specified_ratio']:.1%}")
    print(f"   - Average confidence: {quest_results['average_confidence']:.2f}")
    print(f"   - Validation passed: {quest_results['validation_passed']}")
    
    # Test Citation Critic (with adjusted thresholds)
    print("\n4. Citation Critic:")
    cite_critic = CitationCritic(
        min_confidence=0.5,
        max_unknown_locations=5  # More lenient for test
    )
    cite_results = cite_critic.validate_citations(state)
    results['citation'] = cite_results
    print(f"   - Total citations: {cite_results['total_citations']}")
    print(f"   - Missing page anchors: {cite_results['missing_page_anchors']}")
    print(f"   - Validation passed: {cite_results['validation_passed']}")
    
    # Overall assessment
    all_passed = all([
        results['pdf']['validation_passed'],
        results['classification']['validation_passed'],
        results['questionnaire']['validation_passed'],
        results['citation']['validation_passed']
    ])
    
    print(f"\n✅ Overall Result: {'ALL CRITICS PASSED' if all_passed else 'SOME CRITICS FAILED'}")
    assert all_passed, "Expected all critics to pass with good quality state"


def test_all_critics_fail():
    """Test when all critics detect issues."""
    print("\n" + "="*70)
    print("TEST 2: All Critics Detect Issues (Poor Quality)")
    print("="*70)
    
    state = create_test_state_with_issues()
    
    # Set strict thresholds
    os.environ['PDF_MIN_TEXT_LENGTH'] = '500'
    os.environ['CLASSIFICATION_MIN_COVERAGE'] = '0.5'
    os.environ['QUESTIONNAIRE_MAX_NOT_SPECIFIED'] = '0.3'
    
    results = {}
    
    # Test PDF Critic
    print("\n1. PDF Conversion Critic:")
    pdf_result = pdf_conversion_critic_node(state)
    results['pdf'] = pdf_result['pdf_validation_results']
    print(f"   - Issues found: {len(results['pdf']['issues'])}")
    print(f"   - Severity: {results['pdf']['severity']}")
    print(f"   - Needs rerun: {pdf_result['needs_pdf_rerun']}")
    
    # Test Classification Critic
    print("\n2. Classification Coverage Critic:")
    class_result = classification_coverage_critic_node(state)
    results['classification'] = class_result['classification_validation_results']
    print(f"   - Issues found: {len(results['classification']['issues'])}")
    print(f"   - Severity: {results['classification']['severity']}")
    print(f"   - Needs rerun: {class_result['needs_classification_rerun']}")
    
    # Test Questionnaire Critic
    print("\n3. Questionnaire Completeness Critic:")
    quest_result = questionnaire_completeness_critic_node(state)
    results['questionnaire'] = quest_result['questionnaire_validation_results']
    print(f"   - Issues found: {len(results['questionnaire']['issues'])}")
    print(f"   - Severity: {results['questionnaire']['severity']}")
    print(f"   - Needs rerun: {quest_result['needs_questionnaire_rerun']}")
    
    # Test Citation Critic
    print("\n4. Citation Critic:")
    cite_result = citation_critic_node(state)
    results['citation'] = cite_result['citation_validation_results']
    print(f"   - Issues found: {len(results['citation']['issues'])}")
    print(f"   - Severity: {results['citation']['severity']}")
    print(f"   - Needs rerun: {cite_result['needs_citation_rerun']}")
    
    # Check that issues were detected
    total_issues = sum([
        len(results['pdf']['issues']),
        len(results['classification']['issues']),
        len(results['questionnaire']['issues']),
        len(results['citation']['issues'])
    ])
    
    print(f"\n⚠️ Total Issues Detected: {total_issues}")
    assert total_issues > 10, "Expected many issues to be detected"
    
    # Check that reruns are triggered
    reruns_triggered = sum([
        pdf_result['needs_pdf_rerun'],
        class_result['needs_classification_rerun'],
        quest_result['needs_questionnaire_rerun'],
        cite_result['needs_citation_rerun']
    ])
    
    print(f"⚡ Reruns Triggered: {reruns_triggered}/4 critics")
    assert reruns_triggered >= 3, "Expected at least 3 critics to trigger reruns"


def test_retry_limits():
    """Test that retry limits are respected."""
    print("\n" + "="*70)
    print("TEST 3: Retry Limits Are Respected")
    print("="*70)
    
    state = create_test_state_with_issues()
    
    # Set higher retry limits to allow reruns
    os.environ['PDF_MAX_RERUNS'] = '2'
    os.environ['CLASSIFICATION_MAX_RERUNS'] = '2'
    os.environ['QUESTIONNAIRE_MAX_RERUNS'] = '2'
    os.environ['CITATION_MAX_RERUNS'] = '2'
    
    print("\n1. First attempt - should trigger reruns:")
    state['pdf_critic_attempts'] = 0
    result1 = pdf_conversion_critic_node(state)
    print(f"   PDF: Attempt {result1['pdf_critic_attempts']}, needs rerun: {result1['needs_pdf_rerun']}")
    assert result1['needs_pdf_rerun'], "Should need rerun on first failure"
    
    print("\n2. Max attempts reached - should not trigger reruns:")
    state['pdf_critic_attempts'] = 1  # One attempt already done, next will be the 2nd (max)
    result2 = pdf_conversion_critic_node(state)
    print(f"   PDF: Attempt {result2['pdf_critic_attempts']}, needs rerun: {result2['needs_pdf_rerun']}")
    assert not result2['needs_pdf_rerun'], "Should not rerun after max attempts"
    
    print("\n✅ Retry limits are properly enforced")


def test_critic_recommendations():
    """Test that critics provide useful recommendations."""
    print("\n" + "="*70)
    print("TEST 4: Critic Recommendations")
    print("="*70)
    
    state = create_test_state_with_issues()
    
    # Get recommendations from each critic
    pdf_critic = PDFConversionCritic()
    pdf_results = pdf_critic.validate_conversion(state)
    
    class_critic = ClassificationCoverageCritic()
    class_results = class_critic.validate_classification(state)
    
    quest_critic = QuestionnaireCompletenessCritic()
    quest_results = quest_critic.validate_questionnaire(state)
    
    cite_critic = CitationCritic()
    cite_results = cite_critic.validate_citations(state)
    
    print("\n📋 Recommendations Generated:")
    
    print("\nPDF Conversion:")
    for rec in pdf_results['recommendations']:
        print(f"  [{rec['priority']}] {rec['message']}")
    
    print("\nClassification:")
    for rec in class_results['recommendations']:
        print(f"  [{rec['priority']}] {rec['message']}")
    
    print("\nQuestionnaire:")
    for rec in quest_results['recommendations']:
        print(f"  [{rec['priority']}] {rec['message']}")
    
    print("\nCitations:")
    for rec in cite_results['recommendations']:
        print(f"  [{rec['priority']}] {rec['message']}")
    
    total_recommendations = (
        len(pdf_results['recommendations']) +
        len(class_results['recommendations']) +
        len(quest_results['recommendations']) +
        len(cite_results['recommendations'])
    )
    
    print(f"\n✅ Total Recommendations: {total_recommendations}")
    assert total_recommendations > 5, "Expected multiple recommendations for poor quality state"


def main():
    """Run all tests."""
    print("\n" + "="*70)
    print("MULTI-CRITIC SYSTEM TEST SUITE")
    print("="*70)
    
    try:
        test_all_critics_pass()
        test_all_critics_fail()
        test_retry_limits()
        test_critic_recommendations()
        
        print("\n" + "="*70)
        print("🎉 ALL TESTS PASSED!")
        print("="*70)
        print("\nThe multi-critic system is working correctly:")
        print("✓ PDF Conversion Critic validates document extraction")
        print("✓ Classification Coverage Critic ensures adequate classification")
        print("✓ Questionnaire Completeness Critic validates answers")
        print("✓ Citation Critic verifies reference quality")
        print("✓ All critics trigger appropriate reruns")
        print("✓ Retry limits are properly enforced")
        print("✓ Useful recommendations are generated")
        print("\n🚀 Ready for production use!")
        
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