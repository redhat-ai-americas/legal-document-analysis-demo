#!/usr/bin/env python3
"""
Batch processing script for multiple contract documents.
Processes all documents in the input directory against a reference document.
"""

import argparse
import os
import glob
import yaml
from datetime import datetime
from dotenv import load_dotenv

from workflows.graph_builder import build_graph
from workflows.state import ContractAnalysisState
from utils.state_logger import finalize_logging
from utils.model_config import is_dual_model_enabled

def load_baseline_terms() -> dict:
    """Load baseline terms from YAML file."""
    baseline_path = "prompts/baseline_terms.yaml"
    if os.path.exists(baseline_path):
        with open(baseline_path, 'r') as f:
            baseline_yaml = yaml.safe_load(f)
        return baseline_yaml.get('baseline_summary', {})
    return {}

def get_target_documents(input_dir: str) -> list:
    """Get all processable documents from input directory."""
    supported_extensions = ['*.pdf', '*.md', '*.txt']
    target_files = []
    
    for extension in supported_extensions:
        pattern = os.path.join(input_dir, extension)
        target_files.extend(glob.glob(pattern))
    
    # Also check subdirectories
    for extension in supported_extensions:
        pattern = os.path.join(input_dir, '**', extension)
        target_files.extend(glob.glob(pattern, recursive=True))
    
    # Remove duplicates and sort
    target_files = sorted(list(set(target_files)))
    
    return target_files

def process_single_document(target_file: str, reference_file: str, output_dir: str) -> bool:
    """Process a single target document through the workflow."""
    
    print(f"\n{'='*80}")
    print(f"PROCESSING: {os.path.basename(target_file)}")
    print(f"{'='*80}")
    
    try:
        # Setup paths
        base_dir = os.path.dirname(os.path.abspath(__file__))
        target_document_path = os.path.abspath(target_file)
        reference_document_path = os.path.abspath(reference_file)
        terminology_path = os.path.join(base_dir, 'data', 'templates', 'terminology.yaml')
        spreadsheet_template_path = os.path.join(base_dir, 'data', 'templates', 'contract_analysis_output.csv')
        
        # Generate output filename
        target_filename = os.path.splitext(os.path.basename(target_document_path))[0]
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_filename = f"{target_filename}_analysis_{timestamp}.yaml"
        output_path = os.path.join(output_dir, output_filename)
        
        # Validate input files
        if not os.path.exists(target_document_path):
            print(f"❌ Target file not found: {target_document_path}")
            return False
        if not os.path.exists(reference_document_path):
            print(f"❌ Reference file not found: {reference_document_path}")
            return False
        if not os.path.exists(terminology_path):
            print(f"❌ Terminology file not found: {terminology_path}")
            return False
        
        # Load baseline terms
        baseline_summary = load_baseline_terms()
        
        # Create initial state with all required fields
        initial_state = ContractAnalysisState(
            target_document_path=target_document_path,
            reference_document_path=reference_document_path,
            terminology_path=terminology_path,
            baseline_summary=baseline_summary,
            spreadsheet_template_path=spreadsheet_template_path,
            output_path=output_path,
            processed_document_path="",
            document_text="",
            document_sentences=[],
            reference_document_text="",
            reference_document_sentences=[],
            terminology_data=[],
            classified_sentences=[],
            reference_classified_sentences=[],
            extracted_data={},
            extracted_entities={},
            red_flag_analysis="",
            questionnaire_responses={},
            
            # Dual-model questionnaire responses
            questionnaire_responses_granite={},
            questionnaire_responses_ollama={},
            
            # Model comparison metadata
            model_comparison={},
            
            # Branch tracking
            active_model_branch="both",
            
            final_spreadsheet_row={},
            
            # Enhanced Error Tracking and Quality Metrics
            processing_errors=[],
            quality_metrics={},
            overall_quality_score=None,
            manual_review_required=False,
            processing_warnings=[],
            
            # Workflow Resilience and Checkpointing
            workflow_status="running",
            last_successful_node=None,
            current_processing_node=None,
            checkpoints=[],
            processing_start_time="",
            processing_metadata={},
            
            # Conversion and Fallback Information
            conversion_metadata=None,
            fallback_strategies_used=[],
            api_call_metrics=None,
            
            # Classification Enhancement
            classification_metrics=None
        )
        
        # Build and execute workflow
        dual_model_status = "ENABLED" if is_dual_model_enabled() else "DISABLED"
        print(f"   🤖 Dual-model processing: {dual_model_status}")
        
        app = build_graph()
        final_state = app.invoke(initial_state)
        
        print(f"✅ Successfully processed: {os.path.basename(target_file)}")
        
        # Print summary
        classified_count = len([s for s in final_state.get('classified_sentences', []) if s.get('classes')])
        total_sentences = len(final_state.get('classified_sentences', []))
        questionnaire_count = sum(len(section.get('questions', [])) for section in final_state.get('questionnaire_responses', {}).values())
        
        print(f"   📊 Classified sentences: {classified_count}/{total_sentences}")
        print(f"   📋 Questionnaire responses: {questionnaire_count}")
        
        # Show dual-model comparison if enabled
        if is_dual_model_enabled() and final_state.get('model_comparison'):
            comparison = final_state['model_comparison']
            agreement_rate = comparison.get('agreement_rate', 0) * 100
            questions_compared = comparison.get('questions_compared', 0)
            print(f"   🤝 Model agreement rate: {agreement_rate:.1f}% ({questions_compared} questions)")
        
        print(f"   💾 Output saved to: {output_path}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error processing {os.path.basename(target_file)}: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Main batch processing function."""
    parser = argparse.ArgumentParser(description="Batch process contract documents")
    parser.add_argument(
        "input_dir",
        type=str,
        help="Directory containing target documents to process"
    )
    parser.add_argument(
        "reference_file",
        type=str,
        help="Path to the reference contract file"
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="data/output",
        help="Directory to save output YAML files (default: data/output)"
    )
    parser.add_argument(
    "--max-files",
    type=int,
    default=None,
    help="Maximum number of files to process (for testing)"
    )
    
    parser.add_argument(
       "--rules-file",
       type=str,
       default=None,
       help="Optional path to a rules CSV/XLSX/YAML file to enable rules compliance checking"
    )
    parser.add_argument(
        "--use-template-excel",
        action="store_true",
        help="Write/update master comparison in template format with dynamic rule columns"
    )
    
    args = parser.parse_args()
    
    # Load environment variables
    load_dotenv()
    
    print("🔄 BATCH CONTRACT ANALYSIS")
    print("=" * 50)
    
    # Enable rules mode if provided
    if args.rules_file:
        os.environ['RULES_MODE_ENABLED'] = 'true'
        print(f"Rules mode: ENABLED (rules_file={args.rules_file})")
    else:
        print("Rules mode: DISABLED")

    if args.use_template_excel:
        os.environ['USE_TEMPLATE_EXCEL'] = 'true'
        print("Master Excel template format: ENABLED")
    
    # Validate arguments
    if not os.path.exists(args.input_dir):
        print(f"❌ Input directory not found: {args.input_dir}")
        return 1

    if not os.path.exists(args.reference_file):
        print(f"❌ Reference file not found: {args.reference_file}")
        return 1
    
    # Create output directory if it doesn't exist
    output_dir = os.path.abspath(args.output_dir)
    os.makedirs(output_dir, exist_ok=True)
    
    # Get target documents
    target_files = get_target_documents(args.input_dir)
    
    if not target_files:
        print(f"❌ No processable documents found in: {args.input_dir}")
        print("   Supported formats: PDF, MD, TXT")
        return 1
    
    # Apply max files limit if specified
    if args.max_files:
        target_files = target_files[:args.max_files]
    
    print(f"📁 Found {len(target_files)} documents to process")
    print(f"📂 Reference document: {os.path.basename(args.reference_file)}")
    print(f"💾 Output directory: {output_dir}")
    
    # Process each document
    start_time = datetime.now()
    successful = 0
    failed = 0
    
    for i, target_file in enumerate(target_files, 1):
        print(f"\n🔄 Processing {i}/{len(target_files)}: {os.path.basename(target_file)}")
        
        success = process_single_document(target_file, args.reference_file, output_dir)
        
        if success:
            successful += 1
        else:
            failed += 1
    
    # Final summary
    end_time = datetime.now()
    duration = end_time - start_time
    
    print(f"\n{'='*80}")
    print("BATCH PROCESSING COMPLETE")
    print(f"{'='*80}")
    print(f"📊 Total documents: {len(target_files)}")
    print(f"✅ Successful: {successful}")
    print(f"❌ Failed: {failed}")
    print(f"⏱️  Duration: {duration}")
    print(f"💾 Output directory: {output_dir}")
    
    # Finalize logging
    summary = finalize_logging()
    if summary:
        print(f"📝 Logs saved to: {summary['logs_directory']}")
    
    return 0 if failed == 0 else 1

if __name__ == "__main__":
    exit(main())