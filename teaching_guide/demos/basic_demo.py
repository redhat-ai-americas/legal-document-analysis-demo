#!/usr/bin/env python3
"""
Basic Demo: Simple document analysis workflow demonstration
"""

import os
import sys
import json
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from workflows.graph_builder import build_graph
from datetime import datetime


def run_basic_demo():
    """Demonstrate basic document analysis workflow."""
    
    print("=" * 60)
    print("LEGAL DOCUMENT ANALYSIS - BASIC DEMO")
    print("=" * 60)
    
    # Setup paths
    target_doc = "sample_documents/target_docs/ai_addendum/AI-Services-Addendum-for-Procurement-Contracts-Aug.pdf"
    reference_doc = "sample_documents/standard_docs/ai_addendum/AI-Addendum.md"
    
    print(f"\n📄 Target Document: {Path(target_doc).name}")
    print(f"📄 Reference Document: {Path(reference_doc).name}")
    print(f"⚙️ Rules: Disabled for basic demo")
    
    # Create initial state
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    initial_state = {
        'target_document_path': target_doc,
        'reference_document_path': reference_doc,
        'rules_path': '',  # No rules for basic demo
        'processing_start_time': run_id,
        'run_id': run_id
    }
    
    print(f"\n🚀 Starting analysis (Run ID: {run_id})")
    print("-" * 60)
    
    try:
        # Build and run workflow
        app = build_graph()
        final_state = app.invoke(initial_state)
        
        print("\n✅ Analysis completed successfully!")
        
        # Show summary results
        print("\n📊 RESULTS SUMMARY")
        print("-" * 60)
        
        # Classification results
        classified = final_state.get('classified_sentences', [])
        print(f"Sentences classified: {len(classified)}")
        
        if classified:
            # Count categories
            categories = {}
            for sentence in classified[:50]:  # Sample first 50
                for cat in sentence.get('classes', []):
                    categories[cat] = categories.get(cat, 0) + 1
            
            print("\nTop Classification Categories:")
            for cat, count in sorted(categories.items(), key=lambda x: x[1], reverse=True)[:5]:
                print(f"  - {cat}: {count} occurrences")
        
        # Questionnaire results
        questionnaire = final_state.get('questionnaire_results', {})
        if questionnaire:
            sections = questionnaire.get('sections', [])
            total_questions = sum(len(s.get('questions', [])) for s in sections)
            print(f"\nQuestionnaire questions answered: {total_questions}")
        
        # Output files
        output_dir = f"data/output/runs/run_{run_id}"
        print(f"\n📁 Output files saved to: {output_dir}")
        
        if Path(output_dir).exists():
            files = list(Path(output_dir).glob("*"))
            print("Generated files:")
            for f in files[:5]:  # Show first 5 files
                size = f.stat().st_size
                print(f"  - {f.name} ({size:,} bytes)")
        
        # Show sample classification
        print("\n🔍 SAMPLE CLASSIFICATION")
        print("-" * 60)
        
        if classified:
            sample = classified[0]
            print(f"Sentence: {sample.get('text', '')[:100]}...")
            print(f"Classes: {', '.join(sample.get('classes', []))}")
            print(f"Confidence: {sample.get('confidence', 0):.2f}")
        
        return final_state
        
    except Exception as e:
        print(f"\n❌ Error during analysis: {e}")
        print("\nTroubleshooting tips:")
        print("1. Check your .env file has valid API credentials")
        print("2. Ensure all dependencies are installed: pip install -r requirements.txt")
        print("3. Verify sample documents exist in the correct paths")
        return None


def show_state_file(run_id: str):
    """Display the workflow state file contents."""
    
    state_path = f"data/output/runs/run_{run_id}/workflow_state.json"
    
    if Path(state_path).exists():
        print("\n📋 WORKFLOW STATE")
        print("-" * 60)
        
        with open(state_path) as f:
            state = json.load(f)
        
        metadata = state.get('metadata', {})
        print(f"Status: {metadata.get('status')}")
        print(f"Last Node: {metadata.get('last_node')}")
        print(f"Timestamp: {metadata.get('timestamp')}")
        
        summary = state.get('state_summary', {})
        print("\nProcessing Summary:")
        for key, value in summary.items():
            if value and value != 0:
                print(f"  - {key}: {value}")


def main():
    """Main demo entry point."""
    
    print("\n🎯 This demo will:")
    print("1. Load sample AI addendum documents")
    print("2. Classify all sentences")
    print("3. Answer questionnaire")
    print("4. Generate outputs")
    print("\nPress Enter to continue or Ctrl+C to exit...")
    
    try:
        input()
    except KeyboardInterrupt:
        print("\nDemo cancelled.")
        return
    
    # Run the demo
    result = run_basic_demo()
    
    if result:
        # Show state file
        run_id = result.get('run_id')
        if run_id:
            show_state_file(run_id)
        
        print("\n" + "=" * 60)
        print("DEMO COMPLETE")
        print("=" * 60)
        print("\nNext steps:")
        print("1. Explore the output files in data/output/runs/")
        print("2. Try running with rules enabled")
        print("3. Analyze different documents")
        print("4. Modify the questionnaire")
    else:
        print("\nDemo failed. Please check the error messages above.")


if __name__ == "__main__":
    main()