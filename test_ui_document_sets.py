#!/usr/bin/env python3
"""
Test script to verify the document sets UI functionality
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from ui.streamlit_app import load_document_sets

def test_document_sets():
    """Test loading and validation of document sets"""
    
    print("Testing document sets loading...")
    
    config = load_document_sets()
    document_sets = config.get("document_sets", {})
    
    print(f"\nFound {len(document_sets)} document sets:")
    
    for set_id, set_config in document_sets.items():
        print(f"\n{set_id}: {set_config['name']}")
        print(f"  Description: {set_config.get('description', 'N/A')}")
        print(f"  Reference: {Path(set_config['reference_document']).name}")
        
        if set_config.get('rules_file'):
            print(f"  Rules: {Path(set_config['rules_file']).name}")
        else:
            print(f"  Rules: None")
            
        print(f"  Target documents: {len(set_config.get('target_documents', []))}")
        for target in set_config.get('target_documents', []):
            print(f"    - {target['name']}")
    
    # Verify AI addendum is available
    assert 'ai_addendum' in document_sets, "AI addendum set should be available"
    
    ai_set = document_sets['ai_addendum']
    assert ai_set['reference_document'].endswith('AI-Addendum.md')
    assert ai_set['rules_file'].endswith('ai_addendum_rules.json')
    assert len(ai_set['target_documents']) > 0
    
    print("\n✅ All tests passed!")
    return True

if __name__ == "__main__":
    test_document_sets()