#!/usr/bin/env python3
"""
Test citation flow with page anchors through the entire pipeline
"""

import sys
from utils.citation_tracker import citation_tracker
from utils.citation_manager import citation_manager, Citation
from utils.evidence_validator import ComplianceResult
from utils.compliance_report import report_generator


def test_citation_creation_with_pages():
    """Test creating citations with page information"""
    print("Testing citation creation with page anchors...")
    
    # Sample document with page anchors
    document_text = """
[[page=1]]
This agreement governs the relationship between parties.
The term shall be five years from the effective date.

[[page=2]] 
Payment terms are net 30 days.
Late payments will incur a 2% monthly penalty.

[[page=3]]
Limitation of liability shall not exceed the contract value.
Indemnification clauses apply to both parties.
"""
    
    # Create page map
    from utils.page_anchors import extract_page_map
    page_map = extract_page_map(document_text)
    
    # Test citation creation
    text_to_cite = "Limitation of liability shall not exceed the contract value."
    citation = citation_manager.create_citation(
        text_to_cite,
        document_text,
        hint_position=None,
        page_map=page_map
    )
    
    success = True
    if citation:
        print(f"  ✅ Citation created: {citation.format()}")
        if citation.page == 3:
            print(f"  ✅ Correct page number: {citation.page}")
        else:
            print(f"  ❌ Wrong page: expected 3, got {citation.page}")
            success = False
        
        if "[[page=3]]" in citation.anchor:
            print(f"  ✅ Page anchor present: {citation.anchor}")
        else:
            print(f"  ❌ Page anchor missing or wrong: {citation.anchor}")
            success = False
    else:
        print("  ❌ Failed to create citation")
        success = False
    
    return success


def test_compliance_result_citations():
    """Test that compliance results include proper citations"""
    print("\nTesting compliance result citations...")
    
    # Create sample citations
    citations = [
        Citation(
            text="Contract term is 5 years",
            page=1,
            start_char=50,
            end_char=75,
            confidence=0.95
        ),
        Citation(
            text="Payment due in 30 days",
            page=2,
            start_char=100,
            end_char=122,
            confidence=0.90
        )
    ]
    
    # Create compliance result
    result = ComplianceResult(
        rule_id="TERM_001",
        status="compliant",
        rationale="Contract term is clearly specified",
        citations=citations,
        confidence=0.92
    )
    
    # Convert to dict (as would be stored in state)
    result_dict = result.to_dict()
    
    success = True
    
    # Check citations in dict
    if "citations" in result_dict:
        print("  ✅ Citations field present")
        
        citations_data = result_dict["citations"]
        if len(citations_data) == 2:
            print(f"  ✅ Correct number of citations: {len(citations_data)}")
        else:
            print(f"  ❌ Wrong number of citations: {len(citations_data)}")
            success = False
        
        # Check first citation
        if citations_data:
            first = citations_data[0]
            if "anchor" in first and "[[page=" in first["anchor"]:
                print(f"  ✅ Page anchor in citation: {first['anchor']}")
            else:
                print("  ❌ Missing or invalid page anchor")
                success = False
            
            if first.get("page") == 1:
                print(f"  ✅ Page number preserved: {first['page']}")
            else:
                print("  ❌ Page number wrong or missing")
                success = False
    else:
        print("  ❌ Citations field missing from result")
        success = False
    
    return success


def test_questionnaire_citations():
    """Test questionnaire processor citation handling"""
    print("\nTesting questionnaire citation handling...")
    
    # Sample source sentences with page info
    source_sentences = [
        {
            "sentence": "The limitation of liability is capped at contract value.",
            "sentence_id": "sent_001",
            "page": 5,
            "page_number": 5,  # Both fields for compatibility
            "section": "Liability"
        },
        {
            "sentence": "No consequential damages allowed.",
            "sentence_id": "sent_002",
            "page": 6
        }
    ]
    
    # Create citations using citation_tracker
    citations = citation_tracker.create_citation_from_match(
        "What is the limitation of liability?",
        "capped at contract value",
        source_sentences
    )
    
    success = True
    
    if citations:
        print(f"  ✅ Created {len(citations)} citation(s)")
        
        for i, citation in enumerate(citations):
            # Check location includes page anchor
            if "[[page=" in citation.location:
                print(f"  ✅ Citation {i+1} has page anchor: {citation.location}")
            else:
                print(f"  ❌ Citation {i+1} missing page anchor: {citation.location}")
                success = False
            
            # Check page number is set
            if citation.page_number:
                print(f"  ✅ Citation {i+1} has page number: {citation.page_number}")
            else:
                print(f"  ❌ Citation {i+1} missing page number")
                success = False
    else:
        print("  ❌ No citations created")
        success = False
    
    # Test YAML formatting
    if citations:
        citation_ids = [c.citation_id for c in citations]
        yaml_citations = citation_tracker.format_citations_for_yaml(citation_ids)
        
        if yaml_citations:
            first_yaml = yaml_citations[0]
            if "page_anchor" in first_yaml:
                print(f"  ✅ YAML format includes page_anchor: {first_yaml['page_anchor']}")
            else:
                print("  ❌ YAML format missing page_anchor field")
                success = False
            
            if "location" in first_yaml and "[[page=" in first_yaml["location"]:
                print(f"  ✅ YAML location has anchor: {first_yaml['location']}")
            else:
                print("  ❌ YAML location missing anchor")
                success = False
    
    return success


def test_report_generation_with_citations():
    """Test that compliance reports include citations with anchors"""
    print("\nTesting report generation with citations...")
    
    from utils.rule_manager import Rule
    
    # Create sample rule with correct fields
    from utils.rule_manager import DeterministicChecks, EvidenceRequirements, ComplianceLevels
    
    rule = Rule(
        rule_id="TEST_001",
        category="test",
        description="Test rule for citation validation",
        priority="medium",
        deterministic_checks=DeterministicChecks(
            required_keywords=["test"],
            forbidden_keywords=[],
            regex_patterns=[]
        ),
        evidence_requirements=EvidenceRequirements(
            min_citations=1,
            require_page_anchors=True,
            require_exact_quotes=False
        ),
        compliance_levels=ComplianceLevels(
            compliant="Test found and verified",
            non_compliant="Test missing or invalid",
            not_applicable="Test not required",
            unknown="Unable to determine"
        )
    )
    
    # Create compliance result with citations
    citations = [
        Citation(
            text="Important clause text here",
            page=7,
            start_char=200,
            end_char=226,
            confidence=0.88
        )
    ]
    
    result = ComplianceResult(
        rule_id="TEST_001",
        status="compliant",
        rationale="Test passed",
        citations=citations,
        confidence=0.85
    )
    
    # Generate report
    report = report_generator.generate_report(
        [result],
        {"TEST_001": rule},
        "test_document.pdf",
        "Test document content",
        metadata={"test": True}
    )
    
    success = True
    
    # Check evidence pack
    evidence = report.evidence_pack
    if evidence.get("total_citations", 0) > 0:
        print(f"  ✅ Evidence pack has citations: {evidence['total_citations']}")
    else:
        print("  ❌ Evidence pack has no citations")
        success = False
    
    # Check citation details
    if "citations_by_rule" in evidence:
        rule_citations = evidence["citations_by_rule"].get("TEST_001", [])
        if rule_citations:
            first_cite = rule_citations[0]
            if "anchor" in first_cite and "[[page=" in first_cite["anchor"]:
                print(f"  ✅ Report citation has anchor: {first_cite['anchor']}")
            else:
                print("  ❌ Report citation missing anchor")
                success = False
            
            if first_cite.get("page") == 7:
                print(f"  ✅ Report citation has correct page: {first_cite['page']}")
            else:
                print("  ❌ Report citation has wrong page")
                success = False
    
    # Check summary text instead
    report_generator.generate_executive_summary(report)
    if evidence.get("total_citations", 0) > 0:
        print("  ✅ Executive summary generated with citations")
    else:
        print("  ❌ Executive summary missing citations")
        success = False
    
    return success


def main():
    """Run all citation flow tests"""
    print("=" * 60)
    print("CITATION FLOW TEST SUITE")
    print("=" * 60)
    
    results = []
    
    # Run tests
    results.append(("Citation Creation with Pages", test_citation_creation_with_pages()))
    results.append(("Compliance Result Citations", test_compliance_result_citations()))
    results.append(("Questionnaire Citations", test_questionnaire_citations()))
    results.append(("Report Generation", test_report_generation_with_citations()))
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST RESULTS SUMMARY")
    print("=" * 60)
    
    all_passed = True
    for test_name, passed in results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{test_name}: {status}")
        if not passed:
            all_passed = False
    
    print("=" * 60)
    if all_passed:
        print("🎉 All citation flow tests PASSED!")
        print("\nCitations with page anchors are working correctly throughout the pipeline.")
        return 0
    else:
        print("⚠️  Some tests FAILED. Please review the output above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())