"""
State logging utility for tracking workflow progress and debugging.
Saves state snapshots and error logs with timestamps.
"""

import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional
from pathlib import Path


class StateLogger:
    """
    Handles logging of workflow state and errors with timestamps.
    """
    
    def __init__(self, logs_dir: str = "logs"):
        self.logs_dir = Path(logs_dir)
        self.logs_dir.mkdir(exist_ok=True)
        
        # Create timestamp for this run
        self.run_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Create run-specific directory
        self.run_dir = self.logs_dir / f"run_{self.run_timestamp}"
        self.run_dir.mkdir(exist_ok=True)
        
        # Setup error logging
        self.setup_error_logging()
        
        print(f"State logging initialized. Run ID: {self.run_timestamp}")
        print(f"Logs directory: {self.run_dir}")
    
    def setup_error_logging(self):
        """Setup error logging to file."""
        log_file = self.run_dir / "errors.log"
        
        # Create logger
        self.error_logger = logging.getLogger(f"workflow_errors_{self.run_timestamp}")
        self.error_logger.setLevel(logging.ERROR)
        
        # Create file handler
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.ERROR)
        
        # Create formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(formatter)
        
        # Add handler to logger
        if not self.error_logger.handlers:
            self.error_logger.addHandler(file_handler)
    
    def log_state(self, node_name: str, state: Dict[str, Any], status: str = "completed"):
        """
        Log the current state after a node execution.
        
        Args:
            node_name: Name of the node that was executed
            state: Current workflow state
            status: Status of the node execution (completed, failed, etc.)
        """
        timestamp = datetime.now().isoformat()
        
        # Create state snapshot
        state_snapshot = {
            "timestamp": timestamp,
            "node_name": node_name,
            "status": status,
            "state": self._serialize_state(state)
        }
        
        # Save to timestamped file
        state_file = self.run_dir / f"state_{node_name}_{timestamp.replace(':', '-')}.json"
        
        try:
            with open(state_file, 'w', encoding='utf-8') as f:
                json.dump(state_snapshot, f, indent=2, ensure_ascii=False)
            
            print(f"State logged after {node_name}: {state_file.name}")
            
        except Exception as e:
            self.log_error(f"Failed to log state for {node_name}", e)
    
    def log_error(self, message: str, error: Exception, node_name: Optional[str] = None):
        """
        Log an error with context.
        
        Args:
            message: Error message
            error: The exception that occurred
            node_name: Optional node name where error occurred
        """
        error_info = {
            "timestamp": datetime.now().isoformat(),
            "message": message,
            "error_type": type(error).__name__,
            "error_details": str(error),
            "node_name": node_name
        }
        
        # Log to file
        self.error_logger.error(json.dumps(error_info, indent=2))
        
        # Also save as separate JSON file for easy inspection
        error_file = self.run_dir / f"error_{datetime.now().strftime('%H%M%S')}.json"
        try:
            with open(error_file, 'w', encoding='utf-8') as f:
                json.dump(error_info, f, indent=2, ensure_ascii=False)
        except Exception:
            # Fallback if we can't write the error file
            pass
        
        print(f"Error logged: {message} - {error}")
    
    def _serialize_state(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Serialize state for JSON storage, handling non-serializable objects.
        
        Args:
            state: The state dictionary to serialize
            
        Returns:
            Serializable state dictionary
        """
        serialized = {}
        
        for key, value in state.items():
            try:
                # Try to serialize the value
                json.dumps(value)
                serialized[key] = value
            except TypeError:
                # Handle non-serializable objects
                if hasattr(value, 'to_dict'):
                    serialized[key] = value.to_dict()
                elif hasattr(value, '__dict__'):
                    serialized[key] = {
                        "_type": type(value).__name__,
                        "_repr": repr(value),
                        "_str": str(value)
                    }
                else:
                    serialized[key] = {
                        "_type": type(value).__name__,
                        "_repr": repr(value)
                    }
        
        return serialized
    
    def create_summary(self):
        """Create a summary of the workflow run."""
        summary = {
            "run_id": self.run_timestamp,
            "start_time": self.run_timestamp,
            "end_time": datetime.now().isoformat(),
            "logs_directory": str(self.run_dir),
            "state_files": [],
            "error_files": []
        }
        
        # List all state files
        for state_file in self.run_dir.glob("state_*.json"):
            summary["state_files"].append(state_file.name)
        
        # List all error files
        for error_file in self.run_dir.glob("error_*.json"):
            summary["error_files"].append(error_file.name)
        
        # Check for errors.log
        error_log = self.run_dir / "errors.log"
        if error_log.exists():
            summary["error_log"] = "errors.log"
        
        # Save summary
        summary_file = self.run_dir / "run_summary.json"
        try:
            with open(summary_file, 'w', encoding='utf-8') as f:
                json.dump(summary, f, indent=2, ensure_ascii=False)
            
            print(f"Run summary created: {summary_file}")
            
        except Exception as e:
            print(f"Failed to create run summary: {e}")
        
        return summary


# Global state logger instance
state_logger = None


def initialize_state_logger(logs_dir: str = "logs") -> StateLogger:
    """Initialize the global state logger."""
    global state_logger
    state_logger = StateLogger(logs_dir)
    return state_logger


def log_node_state(node_name: str, state: Dict[str, Any], status: str = "completed"):
    """Log state after node execution."""
    if state_logger:
        state_logger.log_state(node_name, state, status)


def log_node_error(message: str, error: Exception, node_name: Optional[str] = None):
    """Log an error that occurred during node execution."""
    if state_logger:
        state_logger.log_error(message, error, node_name)


def finalize_logging():
    """Create final summary and cleanup."""
    if state_logger:
        return state_logger.create_summary()
    return None