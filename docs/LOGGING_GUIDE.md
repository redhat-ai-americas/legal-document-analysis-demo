# Workflow State Logging & Analysis Guide

## Overview

The legal document analysis workflow includes comprehensive state logging and analysis capabilities to track execution, debug issues, and analyze performance.

## Logging System Architecture

### Dual Logging System

The workflow uses two complementary logging systems:

1. **Standard State Logger** (`utils/state_logger.py`)
   - Creates timestamped state snapshots after each node
   - Logs errors to `errors.log`
   - Maintains backward compatibility

2. **Enhanced State Logger** (`utils/enhanced_state_logger.py`)
   - Tracks node start and completion times
   - Calculates execution duration for each node
   - Creates comprehensive final analysis
   - Generates workflow visualization data
   - Provides state comparison capabilities

## Log Directory Structure

```
logs/
└── run_YYYYMMDD_HHMMSS/
    ├── state_*.json              # State snapshots for each node
    ├── errors.log                # Error log file
    ├── debug.log                 # Debug information
    ├── workflow.log              # Workflow execution log
    ├── error_*.json              # Individual error files
    ├── environment.json          # Environment variables snapshot
    ├── run_summary.json          # Execution summary
    ├── final_state.json          # Complete final state
    └── workflow_visualization.json  # Visualization data
```

## State Files

### State Snapshot Format

Each state file contains:
```json
{
  "timestamp": "2025-08-14T08:00:00.000000",
  "node_name": "questionnaire_processor",
  "status": "completed",
  "execution_order": 7,
  "state": { /* Complete workflow state */ }
}
```

### Final State File

The `final_state.json` contains the complete workflow state after all nodes have executed:
```json
{
  "timestamp": "2025-08-14T08:10:00.000000",
  "run_id": "20250814_080000",
  "state": { /* Complete final state */ }
}
```

## Run Summary

The `run_summary.json` provides a comprehensive overview:

```json
{
  "run_id": "20250814_080000",
  "start_time": "2025-08-14T08:00:00",
  "end_time": "2025-08-14T08:10:00",
  "total_duration_seconds": 600.5,
  "execution_summary": {
    "nodes_executed": 10,
    "execution_order": ["preflight_check", "pdf_converter", ...],
    "node_timings": { /* Duration for each node */ }
  },
  "workflow_analysis": {
    "rules_mode_used": true,
    "pdf_conversion_used": true,
    "reference_comparison_used": true,
    "slowest_node": {"name": "questionnaire_processor", "duration": 120.5},
    "fastest_node": {"name": "preflight_check", "duration": 2.1}
  }
}
```

## Using the Analysis Tool

### Basic Usage

Analyze the most recent run:
```bash
python analyze_run.py
```

Analyze a specific run:
```bash
python analyze_run.py logs/run_20250814_080000
```

### Compare Two Runs

```bash
python analyze_run.py logs/run_20250814_080000 --compare logs/run_20250814_090000
```

### Output Example

```
================================================================================
WORKFLOW RUN ANALYSIS
================================================================================
Run Directory: logs/run_20250814_080000
Run ID: run_20250814_080000

📋 Run Summary Found
  Start Time: 2025-08-14T08:00:00
  End Time: 2025-08-14T08:10:00
  Total Duration: 600.50 seconds

  Execution Details:
    Nodes Executed: 10
    Execution Order: preflight_check → pdf_converter → loader → ...

  Workflow Analysis:
    Rules Mode: ENABLED
    PDF Conversion: YES
    Reference Comparison: YES
    Slowest Node: questionnaire_processor (120.50s)
    Fastest Node: preflight_check (2.10s)

📁 State Files: 10 snapshots

✅ Final State File: Available
  State Keys (45): target_document_path, reference_document_path, ...

✅ No Errors Detected
================================================================================
```

## Debugging Workflow Issues

### 1. Check for Errors

Look for error files:
```bash
ls logs/run_*/error_*.json
cat logs/run_*/errors.log
```

### 2. Examine Node Failures

Find which node failed:
```bash
grep -l "failed" logs/run_*/state_*.json
```

### 3. Compare States

Use the Python API to compare states between nodes:
```python
from utils.enhanced_state_logger import EnhancedStateLogger

logger = EnhancedStateLogger()
comparison = logger.compare_states("target_classifier", "questionnaire_processor")
print(f"Added keys: {comparison['added_keys']}")
print(f"Modified keys: {comparison['modified_keys']}")
```

### 4. Track Rules Mode Execution

Check if rules were used:
```bash
ls logs/run_*/state_rules_loader_*.json
ls logs/run_*/state_rule_compliance_checker_*.json
```

## Performance Analysis

### Node Timing Analysis

The enhanced logger tracks execution time for each node:
```python
# From run_summary.json
"node_timings": {
  "preflight_check": {
    "start": "2025-08-14T08:00:00",
    "end": "2025-08-14T08:00:02",
    "duration_seconds": 2.1
  },
  "questionnaire_processor": {
    "start": "2025-08-14T08:08:00",
    "end": "2025-08-14T08:10:00",
    "duration_seconds": 120.5
  }
}
```

### Identifying Bottlenecks

1. Check the slowest nodes in `run_summary.json`
2. Review state size growth between nodes
3. Analyze API call patterns in slow nodes

## Environment Configuration

The system captures environment variables at runtime:
```json
{
  "RULES_MODE_ENABLED": "true",
  "USE_TUNED_MODEL": "false",
  "DUAL_MODEL_ENABLED": "false",
  "PARALLEL_PROCESSING": "true",
  "MAX_WORKERS": "2"
}
```

## Troubleshooting

### Missing Logs

If logs are missing:
1. Check the `logs/` directory exists
2. Verify write permissions
3. Ensure `initialize_enhanced_logger()` is called in `graph_builder.py`

### State File Too Large

Large state files (>10MB) indicate:
- Accumulating data without cleanup
- Storing full document text multiple times
- Consider implementing state pruning

### Incomplete Runs

For runs that didn't complete:
1. Check the last successful node in state files
2. Review error logs for that node
3. Use `analyze_run.py` to identify the failure point

## Best Practices

1. **Regular Cleanup**: Archive old logs periodically
2. **Monitor Size**: Watch for growing state files
3. **Use Analysis Tool**: Run `analyze_run.py` after each workflow
4. **Compare Runs**: Use comparison feature to track performance changes
5. **Review Summaries**: Check `run_summary.json` for quick insights

## API Reference

### Enhanced State Logger Functions

```python
# Initialize logging
from utils.enhanced_state_logger import initialize_enhanced_logger
logger = initialize_enhanced_logger()

# Log node execution
log_node_start("node_name", state)
log_node_complete("node_name", state, "completed")

# Log errors
log_error("Error message", exception, "node_name")

# Finalize and create summary
summary = finalize_enhanced_logging()

# Get state at specific node
state = logger.get_state_at_node("questionnaire_processor")

# Compare states between nodes
diff = logger.compare_states("node1", "node2")
```

## Future Enhancements

- [ ] Web-based log viewer
- [ ] Real-time workflow monitoring
- [ ] Automated performance regression detection
- [ ] State diff visualization
- [ ] Log aggregation across multiple runs
- [ ] Alert system for failures