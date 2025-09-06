"""
Enhanced node wrapper with comprehensive state tracking and error handling.
"""

from functools import wraps
from typing import Dict, Any, Callable
from utils.enhanced_state_logger import (
    log_node_start, 
    log_node_complete, 
    log_error
)
from utils.state_logger import log_node_state, log_node_error
from utils.classification_output_writer import save_workflow_state


def enhanced_logged_node(node_name: str):
    """
    Enhanced decorator that wraps a node with comprehensive logging.
    
    Args:
        node_name: Name of the node for logging purposes
    """
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(state: Dict[str, Any]) -> Dict[str, Any]:
            print(f"\n{'='*60}")
            print(f"🚀 STARTING NODE: {node_name}")
            print(f"{'='*60}")
            
            # Log node start with enhanced logger
            log_node_start(node_name, state)
            
            # Also use original logger for backward compatibility
            log_node_state(node_name, state, "starting")
            
            try:
                # Execute the node function
                result = func(state)
                
                # Update state with result
                if isinstance(result, dict):
                    updated_state = {**state, **result}
                else:
                    updated_state = state
                
                # Log successful completion with both loggers
                log_node_complete(node_name, updated_state, "completed")
                log_node_state(node_name, updated_state, "completed")
                
                print(f"✅ NODE {node_name} COMPLETED SUCCESSFULLY")
                print(f"{'='*60}\n")
                
                return updated_state
                
            except Exception as e:
                # Log the error with both loggers
                log_error(f"Node {node_name} failed", e, node_name)
                log_node_error(f"Node {node_name} failed", e, node_name)
                
                # Log failed state
                log_node_complete(node_name, state, "failed")
                log_node_state(node_name, state, "failed")
                
                # Save error state to workflow_state.json
                try:
                    run_id = state.get('run_id') or state.get('processing_start_time', '').replace('-', '').replace('T', '_').replace(':', '')[:15]
                    save_workflow_state(
                        state=state,
                        status="error",
                        node_name=node_name,
                        run_id=run_id,
                        error=str(e)
                    )
                except Exception as save_error:
                    print(f"  ⚠️ Could not save error state: {save_error}")
                
                print(f"❌ NODE {node_name} FAILED: {e}")
                print(f"{'='*60}\n")
                
                # Re-raise the exception to maintain workflow behavior
                raise e
        
        return wrapper
    return decorator


def create_enhanced_logged_node(node_func: Callable, node_name: str) -> Callable:
    """
    Create an enhanced logged version of a node function.
    
    Args:
        node_func: The original node function
        node_name: Name for logging
        
    Returns:
        Wrapped function with enhanced logging
    """
    return enhanced_logged_node(node_name)(node_func)