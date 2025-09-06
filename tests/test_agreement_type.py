#!/usr/bin/env python3
"""
Test the agreement_type special handling
"""

from nodes.questionnaire_processor_enhanced import answer_single_question_with_attribution
from workflows.state import ContractAnalysisState

def test_agreement_type_handling():
    """Test that agreement_type question uses special handling."""
    
    # Create a mock state with document metadata
    mock_state: ContractAnalysisState = {
        'target_document_path': '/path/to/Software_License_Agreement.pdf',
        'document_text': 'SOFTWARE LICENSE AGREEMENT\n\nThis Software License Agreement ("Agreement") is entered into...',
        'document_metadata': {
            'document_title': 'SOFTWARE LICENSE AGREEMENT',
            'document_type': 'Software License',
            'document_type_confidence': 0.95,
            'filename': 'Software_License_Agreement.pdf'
        },
        # Add other required fields with defaults
        'questionnaire_path': '',
        'reference_document_path': '',
        'terminology_path': '',
        'baseline_summary': {},
        'spreadsheet_template_path': '',
        'output_path': '',
        'rules_path': None,
        'processed_document_path': '',
        'document_sentences': [],
        'reference_document_text': '',
        'reference_document_sentences': [],
        'terminology_data': [],
        'classified_sentences': [],
        'reference_classified_sentences': [],
        'extracted_data': {},
        'extracted_entities': {},
        'red_flag_analysis': '',
        'questionnaire_responses': {},
        'rule_compliance_results': None,
        'rule_violations': None,
        'compliance_metrics': None,
        'questionnaire_responses_granite': {},
        'questionnaire_responses_ollama': {},
        'model_comparison': {},
        'active_model_branch': 'both',
        'final_spreadsheet_row': {},
        'processing_errors': [],
        'quality_metrics': {},
        'overall_quality_score': None,
        'manual_review_required': False,
        'processing_warnings': [],
        'workflow_status': 'running',
        'last_successful_node': None,
        'current_processing_node': None,
        'checkpoints': [],
        'processing_start_time': '',
        'processing_metadata': {},
        'conversion_metadata': None,
        'fallback_strategies_used': [],
        'api_call_metrics': None,
        'classification_metrics': None,
        'preflight_results': None
    }
    
    # Create a question for agreement_type
    question = {
        'id': 'agreement_type',
        'prompt': 'What type of agreement is this (e.g., Master Agreement, SOW, SaaS)?',
        'guideline': 'Categorize the agreement. Examples: Master, SOW, SaaS, Amendment, Order Form.'
    }
    
    print("Testing agreement_type special handling...")
    print(f"Document path: {mock_state['target_document_path']}")
    print(f"Document title: {mock_state['document_metadata']['document_title']}")
    print(f"Detected type: {mock_state['document_metadata']['document_type']}")
    print()
    
    try:
        # Call the function with agreement_type question
        result = answer_single_question_with_attribution(
            question=question,
            target_sentences=[],  # Should be ignored for agreement_type
            reference_sentences=[],
            terminology_data=[],
            searched_terms=[],
            state=mock_state,
            use_dual_model=False
        )
        
        print("Result:")
        print(f"  Answer: {result.get('answer', 'N/A')}")
        print(f"  Confidence: {result.get('confidence', 0):.1%}")
        print(f"  Used retrieval: {result.get('processing_metadata', {}).get('used_retrieval', True)}")
        
        # Check if special handling was used
        if result.get('processing_metadata', {}).get('type') == 'agreement_type_special':
            print("✅ Special handling was used (no retrieval)")
        else:
            print("❌ Special handling was NOT used")
            
        # Check if the answer makes sense
        answer_lower = result.get('answer', '').lower()
        if 'software' in answer_lower and 'license' in answer_lower:
            print("✅ Correctly identified as Software License Agreement")
        else:
            print(f"⚠️  Answer may not be correct: {result.get('answer')}")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_agreement_type_handling()