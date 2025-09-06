#!/usr/bin/env python3
"""
Test script to verify page anchor flow through the citation pipeline.
"""

import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.citation_tracker import citation_tracker
from utils.sentence_page_mapper import sentence_page_mapper

def test_page_anchor_flow():
    """Test that page anchors flow through the citation system."""
    
    print("Testing Page Anchor Flow Through Citations")
    print("=" * 50)
    
    # 1. Test document text with page anchors
    test_document = """[[page=1]]
This is the first page content.
The agreement begins here.

[[page=2]]
This is the second page content.
Termination clause appears here.

[[page=3]]
This is the third page content.
Liability limitations are described."""
    
    # 2. Extract sentences
    sentences = [
        "This is the first page content.",
        "The agreement begins here.",
        "This is the second page content.",
        "Termination clause appears here.",
        "This is the third page content.",
        "Liability limitations are described."
    ]
    
    # 3. Map sentences to pages
    print("\n1. Testing sentence to page mapping:")
    sentences_with_pages = sentence_page_mapper.map_sentences_to_pages(sentences, test_document)
    
    for item in sentences_with_pages:
        print(f"  Page {item['page']}: {item['sentence'][:50]}...")
    
    # 4. Simulate classified sentences with page info
    classified_sentences = []
    for item in sentences_with_pages:
        classified_sentences.append({
            "sentence": item["sentence"],
            "page": item["page"],
            "page_number": item["page"],  # Include both for compatibility
            "classes": ["termination"] if "termination" in item["sentence"].lower() else ["general"]
        })
    
    # 5. Test citation creation with page info
    print("\n2. Testing citation creation with page anchors:")
    
    # Clear any existing citations
    citation_tracker.citations = {}
    citation_tracker.next_citation_id = 1
    
    # Create citations from classified sentences
    test_answer = "The termination clause appears in the document"
    
    citations = citation_tracker.create_citation_from_match(
        question="What are the termination provisions?",
        answer=test_answer,
        source_sentences=classified_sentences
    )
    
    print(f"  Created {len(citations)} citations")
    for citation in citations:
        print(f"    Citation ID: {citation.citation_id}")
        print(f"    Location: {citation.location}")
        print(f"    Page: {citation.page_number}")
        print(f"    Text: {citation.source_text[:50]}...")
    
    # 6. Test YAML formatting
    print("\n3. Testing YAML format with page anchors:")
    citation_ids = [c.citation_id for c in citations]
    yaml_citations = citation_tracker.format_citations_for_yaml(citation_ids)
    
    for yaml_cite in yaml_citations:
        print("  Citation:")
        print(f"    Type: {yaml_cite['type']}")
        print(f"    Location: {yaml_cite['location']}")
        if 'page_anchor' in yaml_cite:
            print(f"    Page Anchor: {yaml_cite['page_anchor']}")
        print(f"    Confidence: {yaml_cite['confidence']}")
    
    # 7. Verify page anchors are present
    print("\n4. Verification Results:")
    pages_found = sum(1 for c in citations if c.page_number is not None)
    anchors_in_yaml = sum(1 for y in yaml_citations if 'page_anchor' in y)
    
    print(f"  ✓ Citations with page numbers: {pages_found}/{len(citations)}")
    print(f"  ✓ YAML entries with page anchors: {anchors_in_yaml}/{len(yaml_citations)}")
    
    if pages_found == len(citations) and anchors_in_yaml == len(yaml_citations):
        print("\n✅ SUCCESS: Page anchors flow correctly through the citation pipeline!")
    else:
        print("\n⚠️ WARNING: Some page anchors were lost in the pipeline")
    
    return pages_found == len(citations)

if __name__ == "__main__":
    success = test_page_anchor_flow()
    sys.exit(0 if success else 1)