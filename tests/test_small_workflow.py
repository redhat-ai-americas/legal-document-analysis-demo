#!/usr/bin/env python3
"""
Test the complete workflow with a small sample document.
"""

import sys
import os
from dotenv import load_dotenv

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from workflows.graph_builder import build_graph
from workflows.state import ContractAnalysisState

def create_small_test_documents():
    """Create small test documents for quick workflow testing."""
    
    # Small target contract
    target_content = """
    SOFTWARE LICENSING AGREEMENT
    
    This Agreement shall commence on January 1, 2024 and continue for two years.
    Either party may terminate with thirty days notice.
    Customer shall indemnify Provider against third-party claims.
    Provider's liability is limited to amounts paid in preceding twelve months.
    This Agreement may not be assigned without written consent.
    All intellectual property developed shall remain Provider's property.
    """
    
    # Small reference contract
    reference_content = """
    STANDARD CONTRACT TEMPLATE
    
    Initial term is twelve months with automatic renewal.
    Termination requires ninety days written notice.
    Mutual indemnification for direct damages only.
    Liability cap at fees paid in last year.
    Assignment prohibited without consent.
    IP rights remain with original owner.
    """
    
    # Create temporary files
    target_path = "/tmp/small_target.md"
    reference_path = "/tmp/small_reference.md"
    
    with open(target_path, 'w') as f:
        f.write(target_content)
    
    with open(reference_path, 'w') as f:
        f.write(reference_content)
    
    return target_path, reference_path

def main():
    """Run the small workflow test."""
    
    # Load environment variables
    load_dotenv()
    
    print("🧪 Testing Complete Workflow with Small Documents")
    print("=" * 60)
    
    # Create test documents
    target_path, reference_path = create_small_test_documents()
    
    # Create initial state
    initial_state = ContractAnalysisState(
        target_document_path=target_path,
        reference_document_path=reference_path,
        terminology_path="./data/templates/terminology.yaml",
        baseline_summary={},
        spreadsheet_template_path="",
        output_path="/tmp/test_output.csv",
        processed_document_path="",
        document_text="",
        document_sentences=[],
        reference_document_text="",
        reference_document_sentences=[],
        terminology_data=[],
        classified_sentences=[],
        reference_classified_sentences=[],
        extracted_data={},
        red_flag_analysis="",
        questionnaire_responses={},
        final_spreadsheet_row={}
    )
    
    print("📊 Test documents created:")
    print(f"  - Target: {target_path}")
    print(f"  - Reference: {reference_path}")
    
    # Build and run graph
    try:
        print("\n🚀 Building and executing workflow...")
        app = build_graph()
        final_state = app.invoke(initial_state)
        
        print("\n✅ Workflow completed successfully!")
        
        # Display results summary
        print("\n📋 Results Summary:")
        print(f"  - Document sentences: {len(final_state.get('document_sentences', []))}")
        print(f"  - Target classified: {len(final_state.get('classified_sentences', []))}")
        print(f"  - Reference classified: {len(final_state.get('reference_classified_sentences', []))}")
        
        questionnaire_responses = final_state.get('questionnaire_responses', {})
        if questionnaire_responses:
            total_questions = sum(len(section['questions']) for section in questionnaire_responses.values())
            print(f"  - Questionnaire questions answered: {total_questions}")
            
            # Show a few sample answers
            print("\n🔍 Sample Questionnaire Responses:")
            for section_key, section_data in list(questionnaire_responses.items())[:1]:
                for question in section_data['questions'][:3]:
                    print(f"  Q: {question['prompt'][:50]}...")
                    print(f"  A: {question['answer'][:60]}...")
                    print()
        
        return True
        
    except Exception as e:
        print(f"❌ Workflow failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        # Cleanup
        try:
            os.remove(target_path)
            os.remove(reference_path)
        except:
            pass

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)