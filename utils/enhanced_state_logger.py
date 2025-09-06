"""
Enhanced state logging utility with comprehensive workflow tracking and analysis.
Provides detailed state persistence, workflow visualization, and debugging capabilities.
"""

import os
import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional
from pathlib import Path


class EnhancedStateLogger:
    """
    Enhanced state logger with comprehensive tracking and analysis capabilities.
    """
    
    def __init__(self, logs_dir: str = "logs"):
        self.logs_dir = Path(logs_dir)
        self.logs_dir.mkdir(exist_ok=True)
        
        # Create timestamp for this run
        self.run_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Create run-specific directory
        self.run_dir = self.logs_dir / f"run_{self.run_timestamp}"
        self.run_dir.mkdir(exist_ok=True)
        
        # Initialize tracking structures
        self.node_execution_order = []
        self.node_timings = {}
        self.state_snapshots = {}
        self.final_state = {}
        self.workflow_metadata = {
            "run_id": self.run_timestamp,
            "start_time": datetime.now().isoformat(),
            "environment": {},
            "configuration": {}
        }
        
        # Setup logging
        self.setup_logging()
        
        # Load environment configuration
        self.load_environment_config()
        
        print("Enhanced State Logging initialized")
        print(f"Run ID: {self.run_timestamp}")
        print(f"Logs directory: {self.run_dir}")
    
    def setup_logging(self):
        """Setup comprehensive logging system."""
        # Error log
        error_log = self.run_dir / "errors.log"
        self.error_logger = self._create_logger("errors", error_log, logging.ERROR)
        
        # Debug log
        debug_log = self.run_dir / "debug.log"
        self.debug_logger = self._create_logger("debug", debug_log, logging.DEBUG)
        
        # Workflow log
        workflow_log = self.run_dir / "workflow.log"
        self.workflow_logger = self._create_logger("workflow", workflow_log, logging.INFO)
    
    def _create_logger(self, name: str, log_file: Path, level: int) -> logging.Logger:
        """Create a configured logger."""
        logger_name = f"{name}_{self.run_timestamp}"
        logger = logging.getLogger(logger_name)
        logger.setLevel(level)
        
        handler = logging.FileHandler(log_file)
        handler.setLevel(level)
        
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
        
        if not logger.handlers:
            logger.addHandler(handler)
        
        return logger
    
    def load_environment_config(self):
        """Load and log environment configuration."""
        env_vars = {}
        
        # Capture relevant environment variables
        relevant_vars = [
            "RULES_MODE_ENABLED", "USE_TUNED_MODEL", "DUAL_MODEL_ENABLED",
            "COMPARISON_ENABLED", "FORCE_GRANITE", "VALIDATE_HIGH_SEVERITY_ONLY",
            "PARALLEL_PROCESSING", "MAX_WORKERS"
        ]
        
        for var in relevant_vars:
            env_vars[var] = os.environ.get(var, "not_set")
        
        self.workflow_metadata["environment"] = env_vars
        
        # Save environment snapshot
        env_file = self.run_dir / "environment.json"
        with open(env_file, 'w') as f:
            json.dump(env_vars, f, indent=2)
    
    def log_node_start(self, node_name: str, state: Dict[str, Any]):
        """Log the start of a node execution."""
        timestamp = datetime.now()
        
        self.node_execution_order.append(node_name)
        self.node_timings[node_name] = {
            "start": timestamp.isoformat(),
            "end": None,
            "duration_seconds": None
        }
        
        # Log to workflow logger
        self.workflow_logger.info(f"Starting node: {node_name}")
        
        # Save initial state snapshot
        state_file = self.run_dir / f"state_{node_name}_start_{timestamp.strftime('%H%M%S')}.json"
        self._save_state_snapshot(state_file, state, node_name, "started")
    
    def log_node_complete(self, node_name: str, state: Dict[str, Any], status: str = "completed"):
        """Log the completion of a node execution."""
        timestamp = datetime.now()
        
        # Update timing information
        if node_name in self.node_timings:
            start_time = datetime.fromisoformat(self.node_timings[node_name]["start"])
            duration = (timestamp - start_time).total_seconds()
            self.node_timings[node_name]["end"] = timestamp.isoformat()
            self.node_timings[node_name]["duration_seconds"] = duration
            
            self.workflow_logger.info(
                f"Completed node: {node_name} - Status: {status} - Duration: {duration:.2f}s"
            )
        
        # Save complete state snapshot
        state_file = self.run_dir / f"state_{node_name}_{timestamp.strftime('%Y-%m-%dT%H-%M-%S.%f')}.json"
        self._save_state_snapshot(state_file, state, node_name, status)
        
        # Track state changes
        self.state_snapshots[node_name] = {
            "timestamp": timestamp.isoformat(),
            "status": status,
            "state_file": state_file.name
        }
        
        # Update final state
        self.final_state = state.copy()
    
    def log_error(self, message: str, error: Exception, node_name: Optional[str] = None):
        """Log an error with full context."""
        error_info = {
            "timestamp": datetime.now().isoformat(),
            "node": node_name,
            "message": message,
            "error_type": type(error).__name__,
            "error_details": str(error),
            "traceback": self._get_traceback()
        }
        
        # Log to error logger
        self.error_logger.error(json.dumps(error_info, indent=2))
        
        # Save as separate error file
        error_file = self.run_dir / f"error_{node_name}_{datetime.now().strftime('%H%M%S')}.json"
        with open(error_file, 'w') as f:
            json.dump(error_info, f, indent=2)
        
        print(f"❌ Error in {node_name}: {message}")
    
    def _save_state_snapshot(self, file_path: Path, state: Dict[str, Any], 
                            node_name: str, status: str):
        """Save a complete state snapshot."""
        snapshot = {
            "timestamp": datetime.now().isoformat(),
            "node_name": node_name,
            "status": status,
            "execution_order": len(self.node_execution_order),
            "state": self._serialize_state(state)
        }
        
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(snapshot, f, indent=2, ensure_ascii=False)
            
            self.debug_logger.debug(f"State snapshot saved: {file_path.name}")
        except Exception as e:
            self.error_logger.error(f"Failed to save state snapshot: {e}")
    
    def _serialize_state(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Enhanced state serialization with better handling of complex objects."""
        serialized = {}
        
        for key, value in state.items():
            try:
                # Try direct serialization
                json.dumps(value)
                serialized[key] = value
            except (TypeError, ValueError):
                # Handle complex objects
                if value is None:
                    serialized[key] = None
                elif isinstance(value, (list, tuple)):
                    serialized[key] = [self._serialize_value(item) for item in value]
                elif isinstance(value, dict):
                    serialized[key] = self._serialize_state(value)
                elif hasattr(value, 'to_dict'):
                    serialized[key] = value.to_dict()
                elif hasattr(value, '__dict__'):
                    serialized[key] = {
                        "_type": type(value).__name__,
                        "_data": self._serialize_state(value.__dict__)
                    }
                else:
                    serialized[key] = {
                        "_type": type(value).__name__,
                        "_repr": repr(value)[:1000]  # Limit repr length
                    }
        
        return serialized
    
    def _serialize_value(self, value: Any) -> Any:
        """Serialize a single value."""
        try:
            json.dumps(value)
            return value
        except (TypeError, ValueError):
            if hasattr(value, 'to_dict'):
                return value.to_dict()
            elif hasattr(value, '__dict__'):
                return {"_type": type(value).__name__, "_data": value.__dict__}
            else:
                return {"_type": type(value).__name__, "_repr": repr(value)[:500]}
    
    def _get_traceback(self) -> str:
        """Get current traceback as string."""
        import traceback
        return traceback.format_exc()
    
    def create_final_summary(self) -> Dict[str, Any]:
        """Create comprehensive final summary of the workflow run."""
        end_time = datetime.now()
        
        # Calculate total duration
        start_time = datetime.fromisoformat(self.workflow_metadata["start_time"])
        total_duration = (end_time - start_time).total_seconds()
        
        summary = {
            "run_id": self.run_timestamp,
            "start_time": self.workflow_metadata["start_time"],
            "end_time": end_time.isoformat(),
            "total_duration_seconds": total_duration,
            "environment": self.workflow_metadata["environment"],
            "execution_summary": {
                "nodes_executed": len(self.node_execution_order),
                "execution_order": self.node_execution_order,
                "node_timings": self.node_timings,
                "total_nodes": len(set(self.node_execution_order))
            },
            "state_tracking": {
                "snapshots_created": len(self.state_snapshots),
                "final_state_keys": list(self.final_state.keys()),
                "state_size_bytes": len(json.dumps(self._serialize_state(self.final_state)))
            },
            "files_created": {
                "log_directory": str(self.run_dir),
                "state_files": sorted([f.name for f in self.run_dir.glob("state_*.json")]),
                "error_files": sorted([f.name for f in self.run_dir.glob("error_*.json")]),
                "log_files": sorted([f.name for f in self.run_dir.glob("*.log")])
            },
            "workflow_analysis": self._analyze_workflow()
        }
        
        # Save summary
        summary_file = self.run_dir / "run_summary.json"
        with open(summary_file, 'w') as f:
            json.dump(summary, f, indent=2)
        
        # Save final state
        final_state_file = self.run_dir / "final_state.json"
        with open(final_state_file, 'w') as f:
            json.dump({
                "timestamp": end_time.isoformat(),
                "run_id": self.run_timestamp,
                "state": self._serialize_state(self.final_state)
            }, f, indent=2)
        
        # Create workflow visualization data
        self._create_workflow_visualization()
        
        print(f"\n{'='*60}")
        print("WORKFLOW COMPLETED")
        print(f"{'='*60}")
        print(f"Run ID: {self.run_timestamp}")
        print(f"Duration: {total_duration:.2f} seconds")
        print(f"Nodes executed: {len(self.node_execution_order)}")
        print(f"Logs directory: {self.run_dir}")
        print(f"Summary file: {summary_file.name}")
        print(f"Final state: {final_state_file.name}")
        print(f"{'='*60}\n")
        
        return summary
    
    def _analyze_workflow(self) -> Dict[str, Any]:
        """Analyze workflow execution patterns."""
        analysis = {
            "rules_mode_used": "rules_loader" in self.node_execution_order,
            "dual_model_used": any("dual" in node for node in self.node_execution_order),
            "tuned_model_used": any("tuned" in node for node in self.node_execution_order),
            "pdf_conversion_used": "pdf_converter" in self.node_execution_order,
            "reference_comparison_used": "reference_classifier" in self.node_execution_order,
            "slowest_node": None,
            "fastest_node": None,
            "average_node_duration": None
        }
        
        # Find slowest and fastest nodes
        if self.node_timings:
            valid_timings = {
                k: v for k, v in self.node_timings.items() 
                if v.get("duration_seconds") is not None
            }
            
            if valid_timings:
                slowest = max(valid_timings.items(), 
                            key=lambda x: x[1]["duration_seconds"])
                fastest = min(valid_timings.items(), 
                            key=lambda x: x[1]["duration_seconds"])
                
                analysis["slowest_node"] = {
                    "name": slowest[0],
                    "duration": slowest[1]["duration_seconds"]
                }
                analysis["fastest_node"] = {
                    "name": fastest[0],
                    "duration": fastest[1]["duration_seconds"]
                }
                
                durations = [v["duration_seconds"] for v in valid_timings.values()]
                analysis["average_node_duration"] = sum(durations) / len(durations)
        
        return analysis
    
    def _create_workflow_visualization(self):
        """Create data for workflow visualization."""
        viz_data = {
            "nodes": [],
            "edges": [],
            "metadata": {
                "run_id": self.run_timestamp,
                "total_duration": self.node_timings
            }
        }
        
        # Create nodes with timing data
        for i, node in enumerate(self.node_execution_order):
            timing = self.node_timings.get(node, {})
            viz_data["nodes"].append({
                "id": f"{node}_{i}",
                "label": node,
                "order": i,
                "duration": timing.get("duration_seconds", 0),
                "start_time": timing.get("start"),
                "end_time": timing.get("end")
            })
        
        # Create edges showing execution flow
        for i in range(len(self.node_execution_order) - 1):
            viz_data["edges"].append({
                "from": f"{self.node_execution_order[i]}_{i}",
                "to": f"{self.node_execution_order[i+1]}_{i+1}"
            })
        
        # Save visualization data
        viz_file = self.run_dir / "workflow_visualization.json"
        with open(viz_file, 'w') as f:
            json.dump(viz_data, f, indent=2)
    
    def get_state_at_node(self, node_name: str) -> Optional[Dict[str, Any]]:
        """Retrieve the state after a specific node execution."""
        state_files = list(self.run_dir.glob(f"state_{node_name}_*.json"))
        if state_files:
            # Get the most recent state file for this node
            latest_file = max(state_files, key=lambda f: f.stat().st_mtime)
            with open(latest_file, 'r') as f:
                data = json.load(f)
                return data.get("state", {})
        return None
    
    def compare_states(self, node1: str, node2: str) -> Dict[str, Any]:
        """Compare states between two nodes to see what changed."""
        state1 = self.get_state_at_node(node1)
        state2 = self.get_state_at_node(node2)
        
        if not state1 or not state2:
            return {"error": "Could not load states for comparison"}
        
        comparison = {
            "added_keys": list(set(state2.keys()) - set(state1.keys())),
            "removed_keys": list(set(state1.keys()) - set(state2.keys())),
            "modified_keys": [],
            "unchanged_keys": []
        }
        
        for key in set(state1.keys()) & set(state2.keys()):
            if json.dumps(state1[key]) != json.dumps(state2[key]):
                comparison["modified_keys"].append(key)
            else:
                comparison["unchanged_keys"].append(key)
        
        return comparison


# Global enhanced logger instance
enhanced_logger = None


def initialize_enhanced_logger(logs_dir: str = "logs") -> EnhancedStateLogger:
    """Initialize the global enhanced state logger."""
    global enhanced_logger
    enhanced_logger = EnhancedStateLogger(logs_dir)
    return enhanced_logger


def log_node_start(node_name: str, state: Dict[str, Any]):
    """Log the start of a node execution."""
    if enhanced_logger:
        enhanced_logger.log_node_start(node_name, state)


def log_node_complete(node_name: str, state: Dict[str, Any], status: str = "completed"):
    """Log the completion of a node execution."""
    if enhanced_logger:
        enhanced_logger.log_node_complete(node_name, state, status)


def log_error(message: str, error: Exception, node_name: Optional[str] = None):
    """Log an error."""
    if enhanced_logger:
        enhanced_logger.log_error(message, error, node_name)


def finalize_enhanced_logging() -> Optional[Dict[str, Any]]:
    """Create final summary and cleanup."""
    if enhanced_logger:
        return enhanced_logger.create_final_summary()
    return None


def get_current_run_dir() -> Optional[Path]:
    """Get the current run directory path."""
    if enhanced_logger:
        return enhanced_logger.run_dir
    return None