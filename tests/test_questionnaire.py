#!/usr/bin/env python3
"""
Simple test script for questionnaire processing functionality.
"""

import sys
import os
from dotenv import load_dotenv

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from nodes.questionnaire_processor import process_questionnaire
from nodes.document_classifier import classify_reference_sentences as classify_reference_document
from workflows.state import ContractAnalysisState

def create_test_state():
    """Create a minimal test state with sample data."""
    
    # Sample classified sentences for testing
    test_classified_sentences = [
        {"sentence": "This Agreement shall commence on January 1, 2024 and continue for a period of two years.", "classes": ["Term"]},
        {"sentence": "Customer shall indemnify and hold harmless Provider against any third-party claims.", "classes": ["Indemnification"]},
        {"sentence": "All intellectual property developed under this Agreement shall remain the property of Provider.", "classes": ["Intellectual Property"]},
        {"sentence": "Provider's liability shall be limited to the amounts paid by Customer in the twelve months preceding the claim.", "classes": ["Limitation of Liability"]},
        {"sentence": "This Agreement may not be assigned without the prior written consent of both parties.", "classes": ["Assignment"]}
    ]
    
    # Sample terminology data
    test_terminology_data = [
        {"term": "Term", "project_specific_definition": "The duration or time period of the contract"},
        {"term": "Indemnification", "project_specific_definition": "Agreement to compensate for harm or loss"},
        {"term": "Intellectual Property", "project_specific_definition": "Rights to intangible creations of the mind"},
        {"term": "Limitation of Liability", "project_specific_definition": "Clauses that limit financial responsibility"},
        {"term": "Assignment", "project_specific_definition": "Transfer of rights or obligations to another party"}
    ]
    
    # Sample document text
    test_document_text = """
    SOFTWARE LICENSING AGREEMENT
    
    This Software Licensing Agreement ("Agreement") is entered into on January 1, 2024,
    between TechCorp Inc. ("Provider") and CustomerCorp ("Customer").
    
    1. TERM
    This Agreement shall commence on January 1, 2024 and continue for a period of two years,
    automatically renewing for successive one-year terms unless terminated.
    
    2. INTELLECTUAL PROPERTY
    All intellectual property developed under this Agreement shall remain the property of Provider.
    Customer receives a non-exclusive license to use the software.
    
    3. INDEMNIFICATION
    Customer shall indemnify and hold harmless Provider against any third-party claims
    arising from Customer's use of the software.
    
    4. LIABILITY
    Provider's liability shall be limited to the amounts paid by Customer in the twelve
    months preceding the claim.
    
    5. ASSIGNMENT
    This Agreement may not be assigned without the prior written consent of both parties.
    """
    
    # Create temporary reference document
    ref_doc_path = "/tmp/test_reference.txt"
    reference_doc_text = """
    STANDARD SOFTWARE AGREEMENT TEMPLATE
    
    This template provides standard terms for software licensing agreements.
    
    1. TERM AND TERMINATION
    The initial term shall be twelve months with automatic renewal.
    Either party may terminate with ninety days notice.
    
    2. INTELLECTUAL PROPERTY
    All intellectual property rights remain with the original owner.
    Customer receives limited license for internal use only.
    
    3. INDEMNIFICATION 
    Each party shall indemnify the other for damages caused by their breach.
    Indemnification shall be limited to direct damages only.
    
    4. LIABILITY LIMITATIONS
    Total liability shall not exceed the fees paid in the preceding twelve months.
    No party shall be liable for consequential or punitive damages.
    
    5. ASSIGNMENT
    Rights may not be assigned without written consent of both parties.
    """
    
    with open(ref_doc_path, 'w') as f:
        f.write(reference_doc_text)
    
    return ContractAnalysisState(
        target_document_path="/tmp/test_target.txt",
        reference_document_path=ref_doc_path,
        terminology_path="./data/templates/terminology.yaml",
        baseline_summary={},
        spreadsheet_template_path="",
        output_path="",
        processed_document_path="",
        document_text=test_document_text,
        document_sentences=test_document_text.split('.'),
        reference_document_text="",
        reference_document_sentences=[],
        terminology_data=test_terminology_data,
        classified_sentences=test_classified_sentences,
        reference_classified_sentences=[],
        extracted_data={},
        red_flag_analysis="",
        questionnaire_responses={},
        final_spreadsheet_row={}
    )

def main():
    """Run the questionnaire processing test."""
    
    # Load environment variables
    load_dotenv()
    
    print("🧪 Testing Questionnaire Processing")
    print("=" * 50)
    
    # Create test state
    test_state = create_test_state()
    
    print("📊 Test data prepared:")
    print(f"  - Document text: {len(test_state['document_text'])} characters")
    print(f"  - Classified sentences: {len(test_state['classified_sentences'])}")
    print(f"  - Terminology terms: {len(test_state['terminology_data'])}")
    
    # First classify reference document
    print("\n🔍 Classifying reference document...")
    ref_result = classify_reference_document(test_state)
    test_state.update(ref_result)
    
    print(f"  - Reference classified sentences: {len(test_state['reference_classified_sentences'])}")
    
    # Process questionnaire
    try:
        result = process_questionnaire(test_state)
        
        print("\n✅ Questionnaire processing completed!")
        print(f"📋 Sections processed: {len(result['questionnaire_responses'])}")
        
        # Display summary of responses
        total_questions = 0
        for section_key, section_data in result['questionnaire_responses'].items():
            questions_in_section = len(section_data['questions'])
            total_questions += questions_in_section
            print(f"  - {section_data['title']}: {questions_in_section} questions")
        
        print(f"\n📈 Total questions answered: {total_questions}")
        
        # Show a few sample responses
        print("\n🔍 Sample responses:")
        for section_key, section_data in list(result['questionnaire_responses'].items())[:1]:
            for question in section_data['questions'][:3]:
                print(f"  Q: {question['prompt'][:60]}...")
                print(f"  A: {question['answer'][:80]}...")
                print()
        
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)