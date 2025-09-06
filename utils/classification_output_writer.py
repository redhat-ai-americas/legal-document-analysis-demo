#!/usr/bin/env python3
"""
Classification Output Writer

Saves classification results to JSONL format for inspection and analysis.
Each line contains one classified sentence with its metadata.
"""

import json
import os
from typing import List, Dict, Any, Optional
from datetime import datetime


def save_classification_results(
    classified_sentences: List[Dict[str, Any]],
    output_path: str = None,
    run_id: str = None,
    document_name: str = None
) -> str:
    """
    Save classification results to a JSONL file.
    
    Args:
        classified_sentences: List of classified sentence dictionaries
        output_path: Optional specific output path
        run_id: Optional run ID for organizing outputs
        document_name: Name of the document being classified
        
    Returns:
        Path to the saved JSONL file
    """
    # Determine output path
    if output_path is None:
        if run_id:
            # Save in run directory
            run_dir = f"data/output/runs/run_{run_id}"
            os.makedirs(run_dir, exist_ok=True)
            output_path = os.path.join(run_dir, "classified_sentences.jsonl")
        else:
            # Save in data/output with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = f"data/output/classified_sentences_{timestamp}.jsonl"
    
    # Ensure output directory exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    # Write JSONL file
    with open(output_path, 'w', encoding='utf-8') as f:
        for sentence in classified_sentences:
            # Create clean output record
            record = {
                "sentence": sentence.get("sentence", ""),
                "page": sentence.get("page") or sentence.get("page_number"),
                "classes": sentence.get("classes", []),
                "confidence": sentence.get("confidence", 0.0),
                "subsection": sentence.get("subsection", ""),
                "metadata": {
                    "document": document_name or "unknown",
                    "timestamp": datetime.now().isoformat(),
                    "raw_labels": sentence.get("metadata", {}).get("raw_labels", [])
                }
            }
            
            # Add optional fields if present
            if "section_name" in sentence:
                record["section_name"] = sentence["section_name"]
            if "sentence_id" in sentence:
                record["sentence_id"] = sentence["sentence_id"]
                
            # Write as JSON line
            f.write(json.dumps(record, ensure_ascii=False) + '\n')
    
    print(f"📝 Saved {len(classified_sentences)} classified sentences to: {output_path}")
    return output_path


def save_rule_evaluation_results(
    rule_results: List[Dict[str, Any]],
    output_path: str = None,
    run_id: str = None
) -> str:
    """
    Save rule evaluation results to a JSON file.
    
    Args:
        rule_results: List of rule evaluation results
        output_path: Optional specific output path
        run_id: Optional run ID for organizing outputs
        
    Returns:
        Path to the saved JSON file
    """
    # Determine output path
    if output_path is None:
        if run_id:
            # Save in run directory
            run_dir = f"data/output/runs/run_{run_id}"
            os.makedirs(run_dir, exist_ok=True)
            output_path = os.path.join(run_dir, "rule_evaluation_results.json")
        else:
            # Save in data/output with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = f"data/output/rule_evaluation_{timestamp}.json"
    
    # Ensure output directory exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    # Create summary
    summary = {
        "timestamp": datetime.now().isoformat(),
        "total_rules": len(rule_results),
        "results_by_status": {},
        "rules": rule_results
    }
    
    # Count by status
    for rule in rule_results:
        status = rule.get("status", "unknown")
        summary["results_by_status"][status] = summary["results_by_status"].get(status, 0) + 1
    
    # Write JSON file
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    
    print(f"📋 Saved {len(rule_results)} rule evaluation results to: {output_path}")
    return output_path


def save_workflow_state(
    state: Dict[str, Any],
    status: str = "running",
    node_name: str = None,
    run_id: str = None,
    error: str = None
) -> str:
    """
    Save or update the workflow state to a single file.
    
    Args:
        state: Current workflow state
        status: Status of workflow (running, error, completed)
        node_name: Name of the current/last node
        run_id: Optional run ID for organizing outputs
        error: Error message if status is "error"
        
    Returns:
        Path to the saved state file
    """
    # Determine output path
    if run_id:
        state_dir = f"data/output/runs/run_{run_id}"
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        state_dir = f"data/output/runs/run_{timestamp}"
    
    os.makedirs(state_dir, exist_ok=True)
    
    # Always use the same filename - overwrite on each save
    state_file = os.path.join(state_dir, "workflow_state.json")
    
    # Create state data with metadata
    state_data = {
        "metadata": {
            "status": status,
            "last_node": node_name,
            "timestamp": datetime.now().isoformat(),
            "run_id": run_id or datetime.now().strftime("%Y%m%d_%H%M%S"),
            "error": error
        },
        "state_summary": {
            "state_keys": list(state.keys()),
            "document_sentences": len(state.get("document_sentences", [])),
            "classified_sentences": len(state.get("classified_sentences", [])),
            "reference_classified": len(state.get("reference_classified_sentences", [])),
            "rules_evaluated": len(state.get("rule_compliance_results", [])),
            "questionnaire_sections": len(state.get("questionnaire_responses", {})),
            "errors_count": len(state.get("processing_errors", []))
        },
        "state": {}
    }
    
    # Add key state information
    important_keys = [
        "target_document_path",
        "reference_document_path",
        "rules_path",
        "classified_sentences",
        "reference_classified_sentences", 
        "rule_compliance_results",
        "questionnaire_responses",
        "processing_errors",
        "quality_metrics",
        "analysis_data",
        "outputs"
    ]
    
    for key in important_keys:
        if key in state:
            # Serialize the actual data
            try:
                state_data["state"][key] = state[key]
            except Exception:
                # If serialization fails, save summary
                value = state[key]
                if isinstance(value, list):
                    state_data["state"][key] = {
                        "_type": "list_summary",
                        "count": len(value),
                        "sample": str(value[:1]) if value else []
                    }
                elif isinstance(value, dict):
                    state_data["state"][key] = {
                        "_type": "dict_summary",
                        "keys": list(value.keys())[:10],
                        "count": len(value)
                    }
                else:
                    state_data["state"][key] = str(value)[:1000]
    
    # Write state file (overwriting if exists)
    try:
        with open(state_file, 'w', encoding='utf-8') as f:
            json.dump(state_data, f, indent=2, ensure_ascii=False, default=str)
        
        if status == "error":
            print(f"❌ Error state saved to: {state_file}")
        elif status == "completed":
            print(f"✅ Final state saved to: {state_file}")
        # Don't print for normal running status to avoid clutter
            
    except Exception as e:
        print(f"⚠️ Failed to save state: {e}")
    
    return state_file