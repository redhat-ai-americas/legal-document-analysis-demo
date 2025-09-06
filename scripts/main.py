import argparse
import os
from workflows.graph_builder import build_graph
from workflows.state import ContractAnalysisState
from utils.state_logger import finalize_logging
from utils.enhanced_state_logger import finalize_enhanced_logging
from utils.selective_state_logger import finalize_selective_logging
from utils.model_config import is_dual_model_enabled
from dotenv import load_dotenv

def main():
    """
    Main entry point for the contract analysis application.
    """
    # Load environment variables from .env file (e.g., for API keys)
    load_dotenv()
    
    # --- Argument Parsing ---
    parser = argparse.ArgumentParser(description="Automated Contract Analysis Workflow")
    parser.add_argument(
        "target_file", 
        type=str, 
        help="Path to the target contract file to analyze."
    )
    parser.add_argument(
        "reference_file", 
        type=str, 
        help="Path to the reference contract file for comparison."
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
        help="Write/update main comparison in template format with dynamic rule columns"
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress detailed stdout; redirect verbose logs to a timestamped file"
    )
    args = parser.parse_args()

    # --- Configuration ---
    # Define file paths based on the project structure
    script_dir = os.path.dirname(os.path.abspath(__file__))
    base_dir = os.path.dirname(script_dir)  # Go up one level to project root
    # Treat provided paths as absolute or relative to current working directory, not code dir
    target_document_path = os.path.abspath(args.target_file)
    reference_document_path = os.path.abspath(args.reference_file)
    terminology_path = os.path.join(base_dir, 'data', 'templates', 'terminology.yaml')
    spreadsheet_template_path = os.path.join(base_dir, 'data', 'templates', 'Customers.csv')
    
    # Generate a dynamic output file name
    target_filename = os.path.splitext(os.path.basename(target_document_path))[0]
    reference_filename = os.path.splitext(os.path.basename(reference_document_path))[0]
    output_filename = f"Analysis_{target_filename}_vs_{reference_filename}.csv"
    output_path = os.path.join(base_dir, 'data', 'output', output_filename)

    # Check if input files exist
    if not os.path.exists(target_document_path):
        print(f"Error: Target file not found at {target_document_path}")
        return
    if not os.path.exists(reference_document_path):
        print(f"Error: Reference file not found at {reference_document_path}")
        return
    if not os.path.exists(terminology_path):
        print(f"Error: Terminology file not found at {terminology_path}")
        return

    # --- Initial State Setup ---
    initial_state: ContractAnalysisState = {
        "target_document_path": target_document_path,
        "reference_document_path": reference_document_path,
        "terminology_path": terminology_path,
        "baseline_summary": {},  # Required field
        "spreadsheet_template_path": spreadsheet_template_path,
        "output_path": output_path,
        "rules_path": args.rules_file or None,
        "processed_document_path": "",  # Required field
        "document_text": "",
        "document_sentences": [],
        "document_metadata": None,  # Document metadata extraction
        "reference_document_text": "",
        "reference_document_sentences": [],
        "terminology_data": [],
        "classified_sentences": [],
        "reference_classified_sentences": [],
        "extracted_data": {},
        "extracted_entities": {},
        "red_flag_analysis": "",
        "questionnaire_responses": {},
        
        # Model-specific responses (for future multi-model support)
        "questionnaire_responses_granite": None,
        
        # Model metadata
        "model_metadata": None,
        
        "final_spreadsheet_row": {},
        
        # Enhanced Error Tracking and Quality Metrics
        "processing_errors": [],
        "quality_metrics": {},
        "overall_quality_score": None,
        "manual_review_required": False,
        "processing_warnings": [],
        
        # Workflow Resilience and Checkpointing
        "workflow_status": "running",
        "last_successful_node": None,
        "current_processing_node": None,
        "checkpoints": [],
        "processing_start_time": "",
        "processing_metadata": {},
        
        # Conversion and Fallback Information
        "conversion_metadata": None,
        "fallback_strategies_used": [],
        "api_call_metrics": None,
        
        # Classification Enhancement
        "classification_metrics": None
    }

    # --- Graph Execution ---
    # Optional quiet mode: redirect stdout to file, but keep brief console messages
    import sys
    from datetime import datetime as _dt
    quiet_env = os.getenv('LOG_QUIET', 'false').lower() in ('1','true','yes','on')
    quiet_mode = args.quiet or quiet_env
    original_stdout = sys.stdout
    log_file_handle = None
    log_file_path = None
    if quiet_mode:
        logs_dir = os.path.join(base_dir, 'logs')
        os.makedirs(logs_dir, exist_ok=True)
        log_file_path = os.path.join(logs_dir, f"run_stdout_{_dt.now().strftime('%Y%m%d_%H%M%S')}.log")
        log_file_handle = open(log_file_path, 'w', encoding='utf-8')
        sys.stdout = log_file_handle
        original_stdout.write(f"Quiet mode enabled. Detailed logs -> {log_file_path}\n")
        original_stdout.flush()

    print("Building the contract analysis graph...")
    # Enable rules mode if rules file provided
    if args.rules_file:
        os.environ['RULES_MODE_ENABLED'] = 'true'
        print(f"Rules mode: ENABLED (rules_file={args.rules_file})")
    else:
        print("Rules mode: DISABLED")
    if args.use_template_excel:
        os.environ['USE_TEMPLATE_EXCEL'] = 'true'
        print("Master Excel template format: ENABLED")
    dual_model_status = "ENABLED" if is_dual_model_enabled() else "DISABLED"
    print(f"Dual-model processing: {dual_model_status}")
    
    app = build_graph()
    
    print("\nInvoking the graph to start the analysis...")
    try:
        # The graph will stream its print statements as it executes each node
        final_state = app.invoke(initial_state)
        
        print("\n--- WORKFLOW COMPLETE ---")
        print(f"Analysis saved to: {output_path}")
        
        # Check if selective logging is enabled
        use_selective = os.getenv('USE_SELECTIVE_LOGGING', 'true').lower() in ('1', 'true', 'yes', 'on')
        
        if use_selective:
            # Use selective logging (only saves final state and milestones)
            selective_summary = finalize_selective_logging()
            if selective_summary:
                print(f"Logs saved to: {selective_summary['logs_directory']}")
                print(f"Files created: {len(selective_summary['files_created'])}")
                # Show file types
                file_types = {}
                for f in selective_summary['files_created']:
                    file_type = f.get('type', 'other')
                    file_types[file_type] = file_types.get(file_type, 0) + 1
                for ftype, count in file_types.items():
                    print(f"  {ftype}: {count}")
        else:
            # Use full logging (saves all states)
            summary = finalize_logging()
            if summary:
                print(f"Logs saved to: {summary['logs_directory']}")
                print(f"State snapshots: {len(summary['state_files'])}")
                if summary.get('error_files'):
                    print(f"Errors logged: {len(summary['error_files'])}")
            
            # Create enhanced summary with detailed analysis
            enhanced_summary = finalize_enhanced_logging()
            if enhanced_summary:
                print("\n📊 Enhanced Analysis:")
                print(f"  Total duration: {enhanced_summary['total_duration_seconds']:.2f} seconds")
                print(f"  Nodes executed: {enhanced_summary['execution_summary']['nodes_executed']}")
                
                # Show workflow analysis
                analysis = enhanced_summary.get('workflow_analysis', {})
                if analysis.get('rules_mode_used'):
                    print("  Rules mode: USED")
                if analysis.get('slowest_node'):
                    print(f"  Slowest node: {analysis['slowest_node']['name']} ({analysis['slowest_node']['duration']:.2f}s)")
                
                print("  Final state saved: final_state.json")
                print("  Workflow visualization: workflow_visualization.json")
        
        # Print final state for debugging
        # Minimal console summary in quiet mode
        if quiet_mode:
            original_stdout.write("\n--- WORKFLOW COMPLETE ---\n")
            original_stdout.write(f"Analysis saved to: {output_path}\n")
            if log_file_path:
                original_stdout.write(f"Detailed logs: {log_file_path}\n")
            original_stdout.flush()
        else:
            print("\nFinal State:")
            for key, value in final_state.items():
                print(f"{key}: {value}")
            # Return the final state for further processing if needed
            print("\nWorkflow completed successfully.")

        return final_state
        
    except Exception as e:
        print(f"\n❌ WORKFLOW FAILED: {e}")
        
        # Check if selective logging is enabled
        use_selective = os.getenv('USE_SELECTIVE_LOGGING', 'true').lower() in ('1', 'true', 'yes', 'on')
        
        if use_selective:
            # Use selective logging for error case
            selective_summary = finalize_selective_logging()
            if selective_summary:
                print(f"Error logs saved to: {selective_summary['logs_directory']}")
        else:
            # Still create logging summary even on failure
            summary = finalize_logging()
            if summary:
                print(f"Error logs saved to: {summary['logs_directory']}")
            
            # Also create enhanced summary on failure
            enhanced_summary = finalize_enhanced_logging()
            if enhanced_summary:
                print(f"Enhanced error analysis saved to: {enhanced_summary['files_created']['log_directory']}")
        
        raise e
    finally:
        # Restore stdout
        if log_file_handle is not None:
            try:
                sys.stdout = original_stdout
                log_file_handle.close()
            except Exception:
                pass


if __name__ == "__main__":
    main()

#   Usage Examples:
#   # Process all contracts in directory
#   python batch_process.py "data/input" "reference_contract.md"

#   # Limit to 5 files for testing
#   python batch_process.py "data/input" "reference.md" --max-files 5

#   # Custom output directory
#   python batch_process.py "contracts" "ref.md" --output-dir "results"