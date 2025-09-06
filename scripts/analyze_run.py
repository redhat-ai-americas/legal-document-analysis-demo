#!/usr/bin/env python3
"""
Utility script to analyze workflow runs and extract insights from state logs.
"""

import json
import sys
from pathlib import Path
from typing import Dict, Any, Optional
import argparse


def find_latest_run(logs_dir: str = "logs") -> Optional[Path]:
    """Find the most recent run directory."""
    logs_path = Path(logs_dir)
    if not logs_path.exists():
        return None
    
    run_dirs = [d for d in logs_path.iterdir() if d.is_dir() and d.name.startswith("run_")]
    if not run_dirs:
        return None
    
    # Sort by modification time
    latest = max(run_dirs, key=lambda d: d.stat().st_mtime)
    return latest


def load_json_file(file_path: Path) -> Dict[str, Any]:
    """Load a JSON file."""
    try:
        with open(file_path, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading {file_path}: {e}")
        return {}


def analyze_run(run_dir: Path):
    """Analyze a workflow run from its log directory."""
    print(f"\n{'='*80}")
    print("WORKFLOW RUN ANALYSIS")
    print(f"{'='*80}")
    print(f"Run Directory: {run_dir}")
    print(f"Run ID: {run_dir.name}")
    
    # Check for summary files
    summary_file = run_dir / "run_summary.json"
    final_state_file = run_dir / "final_state.json"
    run_dir / "workflow_visualization.json"
    
    # Load and display summary if it exists
    if summary_file.exists():
        print("\n📋 Run Summary Found")
        summary = load_json_file(summary_file)
        
        print(f"  Start Time: {summary.get('start_time', 'N/A')}")
        print(f"  End Time: {summary.get('end_time', 'N/A')}")
        
        if 'total_duration_seconds' in summary:
            duration = summary['total_duration_seconds']
            print(f"  Total Duration: {duration:.2f} seconds")
        
        if 'execution_summary' in summary:
            exec_summary = summary['execution_summary']
            print("\n  Execution Details:")
            print(f"    Nodes Executed: {exec_summary.get('nodes_executed', 0)}")
            print(f"    Execution Order: {' → '.join(exec_summary.get('execution_order', []))}")
        
        if 'workflow_analysis' in summary:
            analysis = summary['workflow_analysis']
            print("\n  Workflow Analysis:")
            print(f"    Rules Mode: {'ENABLED' if analysis.get('rules_mode_used') else 'DISABLED'}")
            print(f"    PDF Conversion: {'YES' if analysis.get('pdf_conversion_used') else 'NO'}")
            print(f"    Reference Comparison: {'YES' if analysis.get('reference_comparison_used') else 'NO'}")
            
            if analysis.get('slowest_node'):
                print(f"    Slowest Node: {analysis['slowest_node']['name']} ({analysis['slowest_node']['duration']:.2f}s)")
            if analysis.get('fastest_node'):
                print(f"    Fastest Node: {analysis['fastest_node']['name']} ({analysis['fastest_node']['duration']:.2f}s)")
    else:
        print("\n⚠️  No run_summary.json found - using fallback analysis")
    
    # Analyze state files
    state_files = sorted(run_dir.glob("state_*.json"))
    print(f"\n📁 State Files: {len(state_files)} snapshots")
    
    if state_files:
        # Group by node
        nodes = {}
        for sf in state_files:
            # Extract node name from filename
            parts = sf.stem.split('_')
            if len(parts) >= 2:
                node_name = '_'.join(parts[1:-1]) if len(parts) > 2 else parts[1]
                if node_name not in nodes:
                    nodes[node_name] = []
                nodes[node_name].append(sf)
        
        print("\n  Nodes with State Snapshots:")
        for node, files in nodes.items():
            print(f"    {node}: {len(files)} snapshot(s)")
    
    # Check for final state
    if final_state_file.exists():
        print("\n✅ Final State File: Available")
        final_state = load_json_file(final_state_file)
        if 'state' in final_state:
            state_keys = list(final_state['state'].keys())
            print(f"  State Keys ({len(state_keys)}): {', '.join(state_keys[:10])}")
            if len(state_keys) > 10:
                print(f"    ... and {len(state_keys) - 10} more")
    else:
        print("\n⚠️  No final_state.json - checking last state file")
        if state_files:
            last_state = load_json_file(state_files[-1])
            if 'state' in last_state:
                print(f"  Last Node: {last_state.get('node_name', 'unknown')}")
                print(f"  Status: {last_state.get('status', 'unknown')}")
    
    # Check for errors
    error_files = list(run_dir.glob("error_*.json"))
    error_log = run_dir / "errors.log"
    
    if error_files or (error_log.exists() and error_log.stat().st_size > 0):
        print("\n❌ Errors Detected:")
        if error_files:
            print(f"  Error JSON files: {len(error_files)}")
            for ef in error_files[:3]:  # Show first 3 errors
                error_data = load_json_file(ef)
                print(f"    - {error_data.get('node_name', 'unknown')}: {error_data.get('message', 'no message')}")
        
        if error_log.exists() and error_log.stat().st_size > 0:
            print(f"  Error log size: {error_log.stat().st_size} bytes")
    else:
        print("\n✅ No Errors Detected")
    
    # Check for output files
    output_dir = run_dir.parent.parent / "data" / "output" / "runs"
    run_output = None
    if output_dir.exists():
        # Find output directory with matching timestamp
        run_timestamp = run_dir.name.replace("run_", "")
        for od in output_dir.iterdir():
            if run_timestamp in od.name:
                run_output = od
                break
    
    if run_output and run_output.exists():
        print("\n📄 Output Files:")
        output_files = list(run_output.glob("*"))
        for of in output_files[:10]:  # Show first 10
            print(f"    - {of.name}")
        if len(output_files) > 10:
            print(f"    ... and {len(output_files) - 10} more files")
    
    print(f"\n{'='*80}\n")


def compare_runs(run1_dir: Path, run2_dir: Path):
    """Compare two workflow runs."""
    print(f"\n{'='*80}")
    print("COMPARING TWO RUNS")
    print(f"{'='*80}")
    
    # Load summaries
    summary1 = load_json_file(run1_dir / "run_summary.json")
    summary2 = load_json_file(run2_dir / "run_summary.json")
    
    # Compare execution
    exec1 = summary1.get('execution_summary', {}).get('execution_order', [])
    exec2 = summary2.get('execution_summary', {}).get('execution_order', [])
    
    print("\nExecution Differences:")
    if exec1 == exec2:
        print("  ✅ Same execution path")
    else:
        print("  ❌ Different execution paths")
        print(f"    Run 1: {' → '.join(exec1[:5])}...")
        print(f"    Run 2: {' → '.join(exec2[:5])}...")
    
    # Compare duration
    dur1 = summary1.get('total_duration_seconds', 0)
    dur2 = summary2.get('total_duration_seconds', 0)
    
    print("\nPerformance Comparison:")
    print(f"  Run 1: {dur1:.2f}s")
    print(f"  Run 2: {dur2:.2f}s")
    if dur1 and dur2:
        diff = dur2 - dur1
        pct = (diff / dur1) * 100
        if diff > 0:
            print(f"  Run 2 is {abs(diff):.2f}s slower ({abs(pct):.1f}%)")
        else:
            print(f"  Run 2 is {abs(diff):.2f}s faster ({abs(pct):.1f}%)")
    
    print(f"\n{'='*80}\n")


def main():
    parser = argparse.ArgumentParser(description="Analyze workflow run logs")
    parser.add_argument(
        "run_dir",
        nargs="?",
        help="Run directory to analyze (defaults to latest)"
    )
    parser.add_argument(
        "--compare",
        help="Compare with another run directory"
    )
    parser.add_argument(
        "--logs-dir",
        default="logs",
        help="Base logs directory (default: logs)"
    )
    
    args = parser.parse_args()
    
    # Determine run directory
    if args.run_dir:
        run_dir = Path(args.run_dir)
    else:
        run_dir = find_latest_run(args.logs_dir)
        if not run_dir:
            print(f"No runs found in {args.logs_dir}")
            sys.exit(1)
    
    if not run_dir.exists():
        print(f"Run directory not found: {run_dir}")
        sys.exit(1)
    
    # Analyze the run
    analyze_run(run_dir)
    
    # Compare if requested
    if args.compare:
        compare_dir = Path(args.compare)
        if not compare_dir.exists():
            print(f"Comparison directory not found: {compare_dir}")
        else:
            compare_runs(run_dir, compare_dir)


if __name__ == "__main__":
    main()