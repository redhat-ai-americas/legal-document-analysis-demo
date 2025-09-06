"""
Selective State Logger - Only logs critical states and errors

Reduces log volume by only saving:
1. Initial state
2. Final state
3. Error states
4. Optional: Key milestone nodes
"""

import os
import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional
from pathlib import Path
from utils.classification_output_writer import save_workflow_state


class SelectiveStateLogger:
    """
    Selective state logger that only saves critical states.
    """
    
    # Define which nodes should always save state (milestones)
    MILESTONE_NODES = {
        'preflight_check',  # Initial validation
        'target_classifier',  # After classification
        'questionnaire_processor',  # After Q&A
        'questionnaire_processor_enhanced',  # Enhanced Q&A
        'yaml_populator'  # Final output
    }
    
    def __init__(self, logs_dir: str = "logs", save_all: bool = False):
        self.logs_dir = Path(logs_dir)
        self.logs_dir.mkdir(exist_ok=True)
        
        # Create timestamp for this run
        self.run_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Create run-specific directory
        self.run_dir = self.logs_dir / f"run_{self.run_timestamp}"
        self.run_dir.mkdir(exist_ok=True)
        
        # Configuration
        self.save_all = save_all  # Override to save everything (for debugging)
        self.has_saved_initial = False
        self.last_state = None
        self.node_count = 0
        
        # Setup error logging
        self.setup_error_logging()
        
        print("Selective State Logging initialized")
        print(f"Run ID: {self.run_timestamp}")
        print(f"Logs directory: {self.run_dir}")
        print(f"Mode: {'SAVE ALL' if save_all else 'SELECTIVE (milestones + errors only)'}")
    
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
    
    def should_save_state(self, node_name: str, status: str) -> bool:
        """
        Determine if state should be saved for this node.
        
        Save if:
        1. save_all is True (debug mode)
        2. It's the first node (initial state)
        3. It's a milestone node
        4. There was an error
        5. It's the final node (will be saved separately)
        """
        if self.save_all:
            return True
            
        if not self.has_saved_initial:
            return True
            
        if status in ['failed', 'error']:
            return True
            
        if node_name in self.MILESTONE_NODES:
            return True
            
        return False
    
    def log_state(self, node_name: str, state: Dict[str, Any], status: str = "completed"):
        """
        Selectively log the current state after a node execution.
        
        Args:
            node_name: Name of the node that was executed
            state: Current workflow state
            status: Status of the node execution (completed, failed, etc.)
        """
        self.node_count += 1
        timestamp = datetime.now().isoformat()
        
        # Store last state for final save
        self.last_state = state
        
        # Check if we should save this state
        if not self.should_save_state(node_name, status):
            print(f"  [Node {self.node_count}] {node_name}: {status} (state not saved - non-milestone)")
            return
        
        # Mark initial as saved
        if not self.has_saved_initial:
            self.has_saved_initial = True
            state_type = "initial"
        elif status in ['failed', 'error']:
            state_type = "error"
        elif node_name in self.MILESTONE_NODES:
            state_type = "milestone"
        else:
            state_type = "checkpoint"
        
        # Use the unified state saving function
        try:
            save_workflow_state(
                state=state,
                status="error" if status in ['failed', 'error'] else "running",
                node_name=node_name,
                run_id=self.run_timestamp,
                error=status if status in ['failed', 'error'] else None
            )
            
            if state_type in ["milestone", "initial", "error"]:
                print(f"  [Node {self.node_count}] {node_name}: {status} ✓ ({state_type} state saved)")
            
        except Exception as e:
            self.log_error(f"Failed to log state for {node_name}", e)
    
    def save_final_state(self):
        """Save the final state of the workflow."""
        if self.last_state:
            try:
                save_workflow_state(
                    state=self.last_state,
                    status="completed",
                    node_name="workflow_complete",
                    run_id=self.run_timestamp,
                    error=None
                )
                print("\n✅ Final state saved: workflow_state.json")
            except Exception as e:
                self.log_error("Failed to save final state", e)
    
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
            "node_name": node_name,
            "node_count": self.node_count
        }
        
        # Log to file
        self.error_logger.error(json.dumps(error_info, indent=2))
        
        # Also save as separate JSON file for easy inspection
        error_file = self.run_dir / f"error_{datetime.now().strftime('%H%M%S')}_{node_name or 'unknown'}.json"
        try:
            with open(error_file, 'w', encoding='utf-8') as f:
                json.dump(error_info, f, indent=2, ensure_ascii=False)
        except Exception:
            pass
        
        print(f"❌ Error logged: {message} - {error}")
    
    def _serialize_state(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Serialize state for JSON storage, with size optimization.
        """
        serialized = {}
        
        # Define fields that can be large and should be truncated
        TRUNCATE_FIELDS = {
            'document_text': 1000,  # First 1000 chars
            'reference_document_text': 1000,
            'document_sentences': 10,  # First 10 sentences
            'reference_document_sentences': 10,
            'classified_sentences': 20,  # First 20 classified
            'reference_classified_sentences': 20
        }
        
        for key, value in state.items():
            try:
                # Check if this field should be truncated
                if key in TRUNCATE_FIELDS:
                    limit = TRUNCATE_FIELDS[key]
                    if isinstance(value, str) and len(value) > limit:
                        serialized[key] = value[:limit] + f"... [truncated, total length: {len(value)}]"
                    elif isinstance(value, list) and len(value) > limit:
                        serialized[key] = value[:limit] + [f"... and {len(value) - limit} more items"]
                    else:
                        serialized[key] = value
                else:
                    # Try to serialize normally
                    json.dumps(value)
                    serialized[key] = value
            except TypeError:
                # Handle non-serializable objects
                if hasattr(value, 'to_dict'):
                    serialized[key] = value.to_dict()
                elif hasattr(value, '__dict__'):
                    serialized[key] = {
                        "_type": type(value).__name__,
                        "_repr": repr(value)[:500]
                    }
                else:
                    serialized[key] = {
                        "_type": type(value).__name__,
                        "_repr": repr(value)[:500]
                    }
        
        return serialized
    
    def create_summary(self):
        """Create a summary of the workflow run."""
        summary = {
            "run_id": self.run_timestamp,
            "start_time": self.run_timestamp,
            "end_time": datetime.now().isoformat(),
            "logs_directory": str(self.run_dir),
            "total_nodes_executed": self.node_count,
            "files_created": []
        }
        
        # List all files created
        for file in self.run_dir.glob("*.json"):
            file_info = {
                "name": file.name,
                "size_bytes": file.stat().st_size,
                "type": "final" if "FINAL" in file.name else 
                       "error" if "error" in file.name else
                       "milestone" if "milestone" in file.name else
                       "initial" if "initial" in file.name else "other"
            }
            summary["files_created"].append(file_info)
        
        # Save summary
        summary_file = self.run_dir / "run_summary.json"
        try:
            with open(summary_file, 'w', encoding='utf-8') as f:
                json.dump(summary, f, indent=2, ensure_ascii=False)
            
            print("\n📊 Run summary created: run_summary.json")
            print(f"   Total files: {len(summary['files_created'])}")
            print(f"   Nodes executed: {self.node_count}")
            
        except Exception as e:
            print(f"Failed to create run summary: {e}")
        
        return summary


# Global selective logger instance
selective_logger = None


def initialize_selective_logger(logs_dir: str = "logs", save_all: bool = False) -> SelectiveStateLogger:
    """Initialize the global selective state logger."""
    global selective_logger
    # Check environment for debug mode
    if os.getenv('DEBUG_SAVE_ALL_STATES', '').lower() in ('1', 'true', 'yes'):
        save_all = True
    selective_logger = SelectiveStateLogger(logs_dir, save_all)
    return selective_logger


def log_selective_state(node_name: str, state: Dict[str, Any], status: str = "completed"):
    """Log state selectively based on importance."""
    if selective_logger:
        selective_logger.log_state(node_name, state, status)


def log_selective_error(message: str, error: Exception, node_name: Optional[str] = None):
    """Log an error that occurred during node execution."""
    if selective_logger:
        selective_logger.log_error(message, error, node_name)


def finalize_selective_logging():
    """Save final state and create summary."""
    if selective_logger:
        selective_logger.save_final_state()
        return selective_logger.create_summary()
    return None