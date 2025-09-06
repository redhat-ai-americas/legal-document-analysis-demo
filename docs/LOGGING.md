# Workflow State Logging

The agentic process workflow now includes comprehensive state logging and error tracking. This helps with debugging, monitoring, and understanding how your workflow progresses through each step.

## What Gets Logged

### State Snapshots

- **After every node execution**: The complete workflow state is saved as JSON
- **Timestamped files**: Each state snapshot includes a timestamp and node name
- **Serialized data**: Non-JSON-serializable objects are converted to readable formats

### Error Tracking

- **API errors**: Granite API failures with retry attempts
- **Node failures**: Any exceptions during node execution
- **Detailed context**: Error type, message, and node where it occurred

## Directory Structure

```
logs/
├── run_20250616_151511/          # Each run gets its own directory
│   ├── state_loader_2025-06-16T15-15-11.json     # State after each node
│   ├── state_classifier_2025-06-16T15-16-23.json
│   ├── errors.log                 # All errors in one log file
│   ├── error_151234.json         # Individual error files for easy parsing
│   └── run_summary.json          # Summary of the entire run
└── run_20250616_143022/          # Previous runs are preserved
```

## Using the Log Viewer

The `utils/log_viewer.py` script provides an easy way to inspect logs:

### View Available Runs

```bash
python utils/log_viewer.py
```

### View Latest Run

```bash
python utils/log_viewer.py --latest
```

### View Specific Run

```bash
python utils/log_viewer.py --run-id 20250616_151511
```

### View Specific Node State

```bash
python utils/log_viewer.py --latest --node classifier
```

### View Only Errors

```bash
python utils/log_viewer.py --latest --errors
```

## State File Format

Each state file contains:

```json
{
  "timestamp": "2025-06-16T15:15:11.436569",
  "node_name": "loader",
  "status": "completed",  // or "failed"
  "state": {
    "target_document_path": "/path/to/document.pdf",
    "document_sentences": ["sentence 1", "sentence 2"],
    "classified_sentences": [
      {"sentence": "...", "classes": ["Term", "Assignment/Change of Control"]}
    ],
    // ... all other state variables
  }
}
```

## Error File Format

Each error file contains:

```json
{
  "timestamp": "2025-06-16T15:15:30.123456",
  "message": "Node classifier failed",
  "error_type": "GraniteServerError",
  "error_details": "Server error 500: Internal server error",
  "node_name": "classifier"
}
```

## Troubleshooting with Logs

### Common Issues

1. **API Failures**: Check for `GraniteServerError` or `GraniteRateLimitError` in error logs
2. **State Corruption**: Compare state progression to see where data gets lost
3. **Performance Issues**: Look at timestamps to identify slow nodes
4. **Classification Problems**: Inspect `classified_sentences` in state files

### Example Debugging Session

```bash
# 1. Check if latest run had errors
python utils/log_viewer.py --latest --errors

# 2. See overall progression
python utils/log_viewer.py --latest

# 3. Check classifier results
python utils/log_viewer.py --latest --node classifier

# 4. Compare before/after a specific node
python utils/log_viewer.py --latest --node loader
python utils/log_viewer.py --latest --node classifier
```

## Integration with Your Workflow

The logging is automatically enabled when you run:

```bash
python main.py document1.pdf document2.pdf
```

At the end of execution, you'll see:

```
--- WORKFLOW COMPLETE ---
Analysis saved to: /path/to/output.csv
Logs saved to: logs/run_20250616_151511
State snapshots: 6
```

## Log Retention

- Logs are **never automatically deleted**
- Each run creates a new timestamped directory
- You can manually clean up old logs if disk space becomes an issue
- Consider keeping logs for at least a few runs for comparison

## Performance Impact

- **Minimal overhead**: State serialization is fast
- **Async logging**: Doesn't slow down your workflow
- **Smart serialization**: Only saves essential data structures

The logging system provides invaluable insights into your workflow execution and makes debugging much easier when dealing with complex contract analysis pipelines.
