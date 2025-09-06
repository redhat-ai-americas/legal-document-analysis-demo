#!/usr/bin/env python3
"""
Base Node Class

Provides a common interface for all workflow nodes with built-in progress reporting,
status updates, and UI communication capabilities.
"""

import time
import traceback
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Callable, List
from datetime import datetime
from enum import Enum
import threading


class NodeStatus(Enum):
    """Node execution statuses"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    RETRYING = "retrying"


class ProgressUpdate:
    """Structured progress update from a node"""
    def __init__(self,
                 node_name: str,
                 status: NodeStatus,
                 message: str,
                 progress: Optional[float] = None,
                 details: Optional[Dict[str, Any]] = None):
        self.node_name = node_name
        self.status = status
        self.message = message
        self.progress = progress  # 0.0 to 1.0
        self.details = details or {}
        self.timestamp = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'node_name': self.node_name,
            'status': self.status.value,
            'message': self.message,
            'progress': self.progress,
            'details': self.details,
            'timestamp': self.timestamp.isoformat()
        }


class ProgressReporter:
    """Thread-safe progress reporter for UI communication"""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance
    
    def __init__(self):
        if not self._initialized:
            self.callbacks: List[Callable] = []
            self.history: List[ProgressUpdate] = []
            self._initialized = True
    
    def register_callback(self, callback: Callable[[ProgressUpdate], None]):
        """Register a callback to receive progress updates"""
        self.callbacks.append(callback)
    
    def report(self, update: ProgressUpdate):
        """Report a progress update to all registered callbacks"""
        self.history.append(update)
        for callback in self.callbacks:
            try:
                callback(update)
            except Exception as e:
                print(f"Error in progress callback: {e}")
    
    def clear_callbacks(self):
        """Clear all registered callbacks"""
        self.callbacks.clear()
    
    def get_history(self) -> List[ProgressUpdate]:
        """Get all progress updates"""
        return self.history.copy()


class BaseNode(ABC):
    """
    Abstract base class for all workflow nodes.
    Provides common functionality for progress reporting and error handling.
    """
    
    def __init__(self, node_name: Optional[str] = None):
        """
        Initialize the base node.
        
        Args:
            node_name: Name of the node for reporting. If not provided, uses class name.
        """
        self.node_name = node_name or self.__class__.__name__
        self.reporter = ProgressReporter()
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None
        self.status = NodeStatus.PENDING
        self.error_message: Optional[str] = None
        
    def report_progress(self,
                       message: str,
                       progress: Optional[float] = None,
                       status: Optional[NodeStatus] = None,
                       details: Optional[Dict[str, Any]] = None):
        """
        Report progress to the UI.
        
        Args:
            message: Human-readable status message
            progress: Progress percentage (0.0 to 1.0)
            status: Current node status
            details: Additional details for the UI
        """
        if status:
            self.status = status
        
        update = ProgressUpdate(
            node_name=self.node_name,
            status=self.status,
            message=message,
            progress=progress,
            details=details
        )
        
        self.reporter.report(update)
        
        # Also print to console for debugging
        progress_str = f" ({progress*100:.0f}%)" if progress is not None else ""
        status_icon = {
            NodeStatus.RUNNING: "🔄",
            NodeStatus.COMPLETED: "✅",
            NodeStatus.FAILED: "❌",
            NodeStatus.SKIPPED: "⏭️",
            NodeStatus.RETRYING: "🔁"
        }.get(self.status, "⏳")
        
        print(f"{status_icon} [{self.node_name}] {message}{progress_str}")
    
    def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the node with automatic progress reporting and error handling.
        
        Args:
            state: The workflow state
            
        Returns:
            Updated workflow state
        """
        self.start_time = time.time()
        self.status = NodeStatus.RUNNING
        
        try:
            # Report start
            self.report_progress(
                f"Starting {self.node_name}",
                progress=0.0,
                status=NodeStatus.RUNNING
            )
            
            # Execute the actual node logic
            state = self.process(state)
            
            # Report completion
            self.end_time = time.time()
            duration = self.end_time - self.start_time
            
            self.report_progress(
                f"Completed in {duration:.1f}s",
                progress=1.0,
                status=NodeStatus.COMPLETED,
                details={'duration': duration}
            )
            
            # Update state with node execution info
            if 'node_execution_history' not in state:
                state['node_execution_history'] = []
            
            state['node_execution_history'].append({
                'node': self.node_name,
                'status': self.status.value,
                'duration': duration,
                'timestamp': datetime.now().isoformat()
            })
            
            return state
            
        except Exception as e:
            # Report failure
            self.end_time = time.time()
            self.error_message = str(e)
            
            self.report_progress(
                f"Failed: {str(e)[:100]}",
                status=NodeStatus.FAILED,
                details={
                    'error': str(e),
                    'traceback': traceback.format_exc()
                }
            )
            
            # Add error to state
            if 'processing_errors' not in state:
                state['processing_errors'] = []
            
            state['processing_errors'].append({
                'node': self.node_name,
                'error': str(e),
                'traceback': traceback.format_exc(),
                'timestamp': datetime.now().isoformat()
            })
            
            # Re-raise or handle based on node configuration
            if self.should_fail_on_error():
                raise
            else:
                return state
    
    @abstractmethod
    def process(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process the node logic. Must be implemented by subclasses.
        
        Args:
            state: The workflow state
            
        Returns:
            Updated workflow state
        """
        pass
    
    def should_fail_on_error(self) -> bool:
        """
        Determine if the node should fail the workflow on error.
        Can be overridden by subclasses.
        
        Returns:
            True if errors should stop the workflow, False to continue
        """
        return True
    
    def validate_inputs(self, state: Dict[str, Any]) -> bool:
        """
        Validate required inputs are present in state.
        Can be overridden by subclasses for specific validation.
        
        Args:
            state: The workflow state
            
        Returns:
            True if inputs are valid
        """
        return True
    
    def report_subtask(self,
                      task_name: str,
                      current: int,
                      total: int,
                      message: Optional[str] = None):
        """
        Report progress for subtasks (e.g., processing multiple items).
        
        Args:
            task_name: Name of the subtask
            current: Current item number
            total: Total number of items
            message: Optional additional message
        """
        progress = current / total if total > 0 else 0
        msg = f"{task_name}: {current}/{total}"
        if message:
            msg += f" - {message}"
        
        self.report_progress(msg, progress=progress)


class BatchProcessingNode(BaseNode):
    """
    Base class for nodes that process items in batches.
    """
    
    def __init__(self, node_name: Optional[str] = None, batch_size: int = 10):
        """
        Initialize batch processing node.
        
        Args:
            node_name: Name of the node
            batch_size: Number of items to process in each batch
        """
        super().__init__(node_name)
        self.batch_size = batch_size
    
    def process_batch(self,
                     items: List[Any],
                     process_func: Callable,
                     task_name: str = "Processing items") -> List[Any]:
        """
        Process items in batches with progress reporting.
        
        Args:
            items: List of items to process
            process_func: Function to process each item
            task_name: Name for progress reporting
            
        Returns:
            List of processed results
        """
        results = []
        total = len(items)
        
        for i in range(0, total, self.batch_size):
            batch = items[i:i + self.batch_size]
            batch_num = i // self.batch_size + 1
            total_batches = (total + self.batch_size - 1) // self.batch_size
            
            self.report_subtask(
                f"{task_name} (Batch {batch_num}/{total_batches})",
                i + len(batch),
                total
            )
            
            for item in batch:
                try:
                    result = process_func(item)
                    results.append(result)
                except Exception as e:
                    self.report_progress(
                        f"Error processing item: {e}",
                        details={'item': str(item)[:100], 'error': str(e)}
                    )
                    results.append(None)
        
        return results


class AsyncNode(BaseNode):
    """
    Base class for nodes that perform asynchronous operations.
    """
    
    def __init__(self, node_name: Optional[str] = None):
        super().__init__(node_name)
        self.async_tasks = []
    
    def add_async_task(self, task: Callable, *args, **kwargs):
        """
        Add an async task to be executed.
        
        Args:
            task: The task function
            *args: Arguments for the task
            **kwargs: Keyword arguments for the task
        """
        self.async_tasks.append((task, args, kwargs))
    
    def wait_for_tasks(self, timeout: Optional[float] = None) -> List[Any]:
        """
        Wait for all async tasks to complete.
        
        Args:
            timeout: Maximum time to wait in seconds
            
        Returns:
            List of task results
        """
        # Implementation would depend on the async framework being used
        # This is a placeholder for the pattern
        results = []
        for task, args, kwargs in self.async_tasks:
            self.report_progress(f"Executing async task: {task.__name__}")
            result = task(*args, **kwargs)
            results.append(result)
        
        self.async_tasks.clear()
        return results