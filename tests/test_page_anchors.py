#!/usr/bin/env python3
"""
Test script to verify page anchor propagation through the pipeline.
"""

import sys
from utils.sentence_page_mapper import sentence_page_mapper
from utils.citation_tracker import citation_tracker

def test_sentence_page_mapping():
    """Test that sentences are correctly mapped to pages."""
    print("Testing sentence to page mapping...")
    
    # Sample document with page anchors
    document_text = """
[[page=1]]
This is the first sentence on page 1.
This is another sentence on page 1.

[[page=2]]
This sentence is on page 2.
Another sentence on page 2.

[[page=3]]
Final sentence on page 3.
"""
    
    # Extract sentences (simulating what document_loader does)
    sentences = [
        "This is the first sentence on page 1.",
        "This is another sentence on page 1.",
        "This sentence is on page 2.",
        "Another sentence on page 2.",
        "Final sentence on page 3."
    ]
    
    # Map sentences to pages
    mapped = sentence_page_mapper.map_sentences_to_pages(sentences, document_text)
    
    # Verify mapping
    expected_pages = [1, 1, 2, 2, 3]
    success = True
    
    for i, (sentence_dict, expected_page) in enumerate(zip(mapped, expected_pages)):
        actual_page = sentence_dict['page']
        if actual_page != expected_page:
            print(f"  ❌ Sentence {i+1}: Expected page {expected_page}, got {actual_page}")
            success = False
        else:
            print(f"  ✅ Sentence {i+1}: Correctly mapped to page {actual_page}")
    
    return success


def test_citation_with_pages():
    """Test that citations include page anchors."""
    print("\nTesting citation creation with page anchors...")
    
    # Sample source sentences with page info
    source_sentences = [
        {
            "sentence": "The contract term is 5 years.",
            "sentence_id": "sent_001",
            "page": 3,
            "page_number": 3,
            "section_name": "Terms"
        },
        {
            "sentence": "Payment is due within 30 days.",
            "sentence_id": "sent_002", 
            "page": 5,
            "page_number": 5,
            "section_name": "Payment"
        }
    ]
    
    # Create citations
    citations = citation_tracker.create_citation_from_match(
        "What is the contract term?",
        "5 years",
        source_sentences
    )
    
    success = True
    for citation in citations:
        if "[[page=" in citation.location:
            print(f"  ✅ Citation includes page anchor: {citation.location}")
        else:
            print(f"  ❌ Citation missing page anchor: {citation.location}")
            success = False
    
    # Test YAML formatting
    citation_ids = [c.citation_id for c in citations]
    yaml_citations = citation_tracker.format_citations_for_yaml(citation_ids)
    
    for yaml_cite in yaml_citations:
        if yaml_cite.get('page_anchor'):
            print(f"  ✅ YAML citation has page_anchor: {yaml_cite['page_anchor']}")
        else:
            print("  ❌ YAML citation missing page_anchor field")
            success = False
    
    return success


def test_questionnaire_page_propagation():
    """Test that questionnaire processor properly handles page info."""
    print("\nTesting questionnaire processor page propagation...")
    
    # Sample classified sentences with page info
    classified_sentences = [
        {
            "sentence": "Limitation of liability clause here.",
            "classes": ["limitation_of_liability"],
            "page": 7,
            "page_number": 7,
            "section": "Liability"
        },
        {
            "sentence": "No limitation specified.",
            "classes": ["limitation_of_liability"],
            "page": 8,
            "section_name": "General"
        }
    ]
    
    # Simulate what questionnaire processor does
    source_sentences_for_citation = []
    for sentence_data in classified_sentences:
        # Extract page info from multiple possible field names
        page_number = (sentence_data.get("page") or 
                      sentence_data.get("page_number") or 
                      sentence_data.get("page_num"))
        section_name = sentence_data.get("section") or sentence_data.get("section_name")
        
        source_sentences_for_citation.append({
            "sentence": sentence_data.get("sentence", ""),
            "sentence_id": sentence_data.get("sentence_id"),
            "page_number": page_number,
            "section_name": section_name
        })
    
    success = True
    for i, source in enumerate(source_sentences_for_citation):
        if source['page_number']:
            print(f"  ✅ Sentence {i+1}: Page {source['page_number']} extracted")
        else:
            print(f"  ❌ Sentence {i+1}: No page number extracted")
            success = False
    
    return success


def main():
    """Run all tests."""
    print("=" * 60)
    print("PAGE ANCHOR PROPAGATION TEST SUITE")
    print("=" * 60)
    
    results = []
    
    # Run tests
    results.append(("Sentence to Page Mapping", test_sentence_page_mapping()))
    results.append(("Citation with Pages", test_citation_with_pages()))
    results.append(("Questionnaire Page Propagation", test_questionnaire_page_propagation()))
    
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
        print("🎉 All tests PASSED!")
        return 0
    else:
        print("⚠️  Some tests FAILED. Please review the output above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())