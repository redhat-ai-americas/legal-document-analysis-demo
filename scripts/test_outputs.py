#!/usr/bin/env python3
"""
Test script to verify output file generation
"""

import os
import sys
import json
from pathlib import Path

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from workflows.graph_builder import build_graph
from workflows.state import ContractAnalysisState

def test_classification_outputs():
    """Test that classification outputs are being saved correctly"""
    
    print("="*60)
    print("TESTING OUTPUT FILE GENERATION")
    print("="*60)
    
    # Use a simple test document
    test_doc = "sample_documents/standard_docs/ai_addendum/AI-Addendum.md"
    
    # Build minimal graph (just classification)
    os.environ['RULES_MODE_ENABLED'] = 'false'  # Disable rules for speed
    
    graph = build_graph()
    
    # Create initial state
    initial_state = {
        'target_document_path': test_doc,
        'reference_document_path': '',  # No reference for this test
        'rules_path': '',
        'processing_start_time': '20250905_230000',  # Fixed timestamp for testing
        'run_id': '20250905_230000'
    }
    
    print(f"\nTest document: {test_doc}")
    print("Running workflow (classification only)...\n")
    
    try:
        # Run just the first few nodes
        # We'll interrupt after classification
        import signal
        import threading
        
        def timeout_handler():
            print("\n⏱️ Stopping after classification phase...")
            os._exit(0)
        
        # Set a timer to stop after 30 seconds
        timer = threading.Timer(30.0, timeout_handler)
        timer.start()
        
        # Run the workflow
        final_state = graph.invoke(initial_state)
        
        timer.cancel()
        
    except SystemExit:
        pass
    except Exception as e:
        print(f"Workflow stopped: {e}")
    
    # Check what files were created
    print("\n" + "="*60)
    print("CHECKING OUTPUT FILES")
    print("="*60)
    
    run_dir = f"data/output/runs/run_{initial_state['run_id']}"
    
    expected_files = [
        f"{run_dir}/workflow_state.json",
        f"{run_dir}/classified_sentences.jsonl",
        f"{run_dir}/rule_evaluation_results.json"  # Only if rules enabled
    ]
    
    for file_path in expected_files:
        if os.path.exists(file_path):
            size = os.path.getsize(file_path)
            print(f"✅ Found: {os.path.basename(file_path)} ({size:,} bytes)")
            
            # Show sample content
            if file_path.endswith('.jsonl'):
                with open(file_path, 'r') as f:
                    lines = f.readlines()
                    print(f"   Contains {len(lines)} classified sentences")
                    if lines:
                        first = json.loads(lines[0])
                        print(f"   Sample: {first.get('sentence', '')[:80]}...")
                        print(f"   Classes: {first.get('classes', [])}")
            
            elif file_path.endswith('workflow_state.json'):
                with open(file_path, 'r') as f:
                    state = json.load(f)
                    metadata = state.get('metadata', {})
                    summary = state.get('state_summary', {})
                    print(f"   Status: {metadata.get('status')}")
                    print(f"   Last node: {metadata.get('last_node')}")
                    print(f"   Sentences classified: {summary.get('classified_sentences', 0)}")
        else:
            if 'rule_evaluation' in file_path and os.environ.get('RULES_MODE_ENABLED') == 'false':
                print(f"⏭️ Skipped: {os.path.basename(file_path)} (rules disabled)")
            else:
                print(f"❌ Missing: {os.path.basename(file_path)}")
    
    # Check log directory
    log_dir = f"logs/run_{initial_state['processing_start_time']}"
    if os.path.exists(log_dir):
        print(f"\n📁 Log directory: {log_dir}")
        for file in os.listdir(log_dir):
            size = os.path.getsize(os.path.join(log_dir, file))
            print(f"   - {file} ({size:,} bytes)")
    
    print("\n" + "="*60)
    print("TEST COMPLETE")
    print("="*60)

if __name__ == "__main__":
    test_classification_outputs()