#!/usr/bin/env python3
"""
Test script to verify all enhancements are working:
1. Selective state logging (reduced file count)
2. Enhanced confidence scoring with method tracking
3. Decision attribution in YAML output
"""

import os
import yaml
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


def check_environment():
    """Check environment variables are set correctly."""
    print("Checking environment settings...")
    
    env_vars = {
        'USE_SELECTIVE_LOGGING': os.getenv('USE_SELECTIVE_LOGGING', 'true'),
        'USE_ENHANCED_ATTRIBUTION': os.getenv('USE_ENHANCED_ATTRIBUTION', 'false'),
        'RULES_MODE_ENABLED': os.getenv('RULES_MODE_ENABLED', 'false')
    }
    
    print("Environment settings:")
    for key, value in env_vars.items():
        print(f"  {key}: {value}")
    
    if env_vars['USE_SELECTIVE_LOGGING'].lower() not in ('1', 'true', 'yes', 'on'):
        print("  ⚠️  Selective logging is OFF - will generate many log files")
    else:
        print("  ✅ Selective logging is ON - minimal file generation")
    
    if env_vars['USE_ENHANCED_ATTRIBUTION'].lower() not in ('1', 'true', 'yes', 'on'):
        print("  ⚠️  Enhanced attribution is OFF - no decision tracking")
    else:
        print("  ✅ Enhanced attribution is ON - full decision tracking")
    
    return env_vars


def check_log_files(run_timestamp=None):
    """Check the number and types of log files generated."""
    print("\nChecking log files...")
    
    logs_dir = (Path(__file__).resolve().parent.parent / "logs").resolve()
    if not logs_dir.exists():
        print("  No logs directory found")
        return None
    
    # Find the most recent run directory
    run_dirs = sorted([d for d in logs_dir.iterdir() if d.is_dir() and d.name.startswith("run_")])
    if not run_dirs:
        print("  No run directories found")
        return None
    
    latest_run = run_dirs[-1]
    print(f"  Latest run: {latest_run.name}")
    
    # Count files by type
    files = list(latest_run.glob("*.json"))
    file_types = {}
    for f in files:
        if "FINAL" in f.name:
            ftype = "final"
        elif "error" in f.name:
            ftype = "error"
        elif "milestone" in f.name:
            ftype = "milestone"
        elif "initial" in f.name:
            ftype = "initial"
        else:
            ftype = "other"
        file_types[ftype] = file_types.get(ftype, 0) + 1
    
    print(f"  Total files: {len(files)}")
    for ftype, count in sorted(file_types.items()):
        print(f"    {ftype}: {count}")
    
    # Check if selective logging worked
    if len(files) > 20:
        print("  ⚠️  Too many log files - selective logging might not be working")
    else:
        print("  ✅ Log file count is reasonable")
    
    return latest_run


def check_yaml_output():
    """Check if YAML output contains enhanced attribution."""
    print("\nChecking YAML output...")
    
    output_dir = (Path(__file__).resolve().parent.parent / "data" / "output").resolve()
    if not output_dir.exists():
        print("  No output directory found")
        return None
    
    # Find the most recent YAML file
    yaml_files = sorted(output_dir.glob("*.yaml"), key=lambda p: p.stat().st_mtime)
    if not yaml_files:
        print("  No YAML files found")
        return None
    
    latest_yaml = yaml_files[-1]
    print(f"  Latest YAML: {latest_yaml.name}")
    
    with open(latest_yaml, 'r') as f:
        data = yaml.safe_load(f)
    
    # Check for enhanced fields
    has_extraction_confidence = False
    has_decision_attribution = False
    has_confidence_method = False
    
    # Navigate through the YAML structure
    for section in ['document_information', 'key_clause_analysis', 'gaps_and_comments']:
        if section in data:
            for key, value in data[section].items():
                if isinstance(value, dict):
                    if 'extraction_confidence' in value:
                        has_extraction_confidence = True
                        # Check if confidence method is included
                        if 'confidence_method' in value.get('extraction_confidence', {}):
                            has_confidence_method = True
                    if 'decision_attribution' in value:
                        has_decision_attribution = True
    
    print("  Enhanced fields present:")
    print(f"    extraction_confidence: {'✅' if has_extraction_confidence else '❌'}")
    print(f"    confidence_method: {'✅' if has_confidence_method else '❌'}")
    print(f"    decision_attribution: {'✅' if has_decision_attribution else '❌'}")
    
    if has_extraction_confidence and has_confidence_method and has_decision_attribution:
        print("  ✅ All enhanced fields are present in YAML")
    else:
        print("  ⚠️  Some enhanced fields are missing")
    
    return data


def check_confidence_methods(yaml_data):
    """Check what confidence methods were used."""
    print("\nChecking confidence calculation methods...")
    
    methods_used = {}
    
    for section in ['document_information', 'key_clause_analysis', 'gaps_and_comments']:
        if section in yaml_data:
            for key, value in yaml_data[section].items():
                if isinstance(value, dict) and 'extraction_confidence' in value:
                    conf_data = value['extraction_confidence']
                    if 'confidence_method' in conf_data:
                        method = conf_data['confidence_method']
                        methods_used[method] = methods_used.get(method, 0) + 1
    
    if methods_used:
        print("  Confidence methods used:")
        for method, count in sorted(methods_used.items()):
            print(f"    {method}: {count}")
    else:
        print("  No confidence methods found in output")
    
    return methods_used


def check_decision_tracking(yaml_data):
    """Check decision attribution details."""
    print("\nChecking decision attribution...")
    
    decisions_found = {
        'deterministic': 0,
        'no_clauses_found': 0,
        'llm_decision': 0,
        'error': 0
    }
    
    llms_used = {}
    
    for section in ['document_information', 'key_clause_analysis', 'gaps_and_comments']:
        if section in yaml_data:
            for key, value in yaml_data[section].items():
                if isinstance(value, dict) and 'decision_attribution' in value:
                    attr = value['decision_attribution']
                    if 'decision_method' in attr:
                        method = attr['decision_method']
                        if method in decisions_found:
                            decisions_found[method] += 1
                    
                    if 'llm_name' in attr and attr['llm_name']:
                        llm = attr['llm_name']
                        llms_used[llm] = llms_used.get(llm, 0) + 1
    
    print("  Decision methods:")
    for method, count in sorted(decisions_found.items()):
        if count > 0:
            print(f"    {method}: {count}")
    
    if llms_used:
        print("  LLMs used:")
        for llm, count in sorted(llms_used.items()):
            print(f"    {llm}: {count}")
    
    total_decisions = sum(decisions_found.values())
    if total_decisions > 0:
        print(f"  ✅ Found {total_decisions} decision attributions")
    else:
        print("  ⚠️  No decision attributions found")


def main():
    """Run all checks."""
    print("=" * 60)
    print("Testing Contract Analysis Enhancements")
    print("=" * 60)
    
    # Check environment
    env_vars = check_environment()
    
    # Check log files
    check_log_files()
    
    # Check YAML output
    yaml_data = check_yaml_output()
    
    if yaml_data:
        # Check confidence methods
        check_confidence_methods(yaml_data)
        
        # Check decision tracking
        check_decision_tracking(yaml_data)
    
    print("\n" + "=" * 60)
    print("Summary:")
    
    if env_vars['USE_SELECTIVE_LOGGING'].lower() in ('1', 'true', 'yes', 'on'):
        print("✅ Selective logging is enabled")
    else:
        print("❌ Selective logging is disabled")
    
    if env_vars['USE_ENHANCED_ATTRIBUTION'].lower() in ('1', 'true', 'yes', 'on'):
        print("✅ Enhanced attribution is enabled")
    else:
        print("❌ Enhanced attribution is disabled")
    
    if yaml_data:
        print("✅ YAML output was generated")
    else:
        print("⚠️  No YAML output found - run the workflow first")
    
    print("=" * 60)


if __name__ == "__main__":
    main()