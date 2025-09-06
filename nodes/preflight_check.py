"""
Preflight check node to test model endpoint connectivity.

This node tests all model endpoints used in the workflow to ensure they are
accessible before processing begins. It uses the same adapters as other nodes
to ensure accurate connectivity testing.
"""

import time
from typing import Dict, Any, List, Optional
from datetime import datetime
from workflows.state import ContractAnalysisState
from utils.granite_client import granite_client, GraniteAPIError
import os
import yaml
from utils.error_handler import handle_node_errors


class ModelEndpointTest:
    """Individual model endpoint test result."""
    
    def __init__(self, name: str, status: str, response_time: float = 0.0, 
                 error: Optional[str] = None, response: Optional[str] = None):
        self.name = name
        self.status = status  # 'success', 'error', 'timeout'
        self.response_time = response_time
        self.error = error
        self.response = response
        self.timestamp = datetime.now().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging."""
        return {
            'name': self.name,
            'status': self.status,
            'response_time_ms': round(self.response_time * 1000, 2),
            'error': self.error,
            'response_preview': self.response[:100] if self.response else None,
            'timestamp': self.timestamp
        }


def _load_preflight_prompts() -> Dict[str, str]:
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(base_dir, "prompts", "preflight.yaml")
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
            return {
                "basic_ok": data.get("basic_ok", "Hello, this is a preflight connectivity test. Please respond with 'OK'."),
                "json_capability": data.get("json_capability", "Please respond with valid JSON in this exact format:\n{\"term\": \"test\", \"subsection\": \"This is a test response\"}")
            }
    except Exception:
        return {
            "basic_ok": "Hello, this is a preflight connectivity test. Please respond with 'OK'.",
            "json_capability": "Please respond with valid JSON in this exact format:\n{\"term\": \"test\", \"subsection\": \"This is a test response\"}"
        }


def test_granite_endpoint() -> ModelEndpointTest:
    """Test Granite API endpoint connectivity."""
    prompts = _load_preflight_prompts()
    test_prompt = prompts["basic_ok"]
    
    start_time = time.time()
    try:
        response = granite_client.call_api(
            prompt=test_prompt,
            max_tokens=10,
            temperature=0.0,
            return_metadata=False
        )
        response_time = time.time() - start_time
        
        response_str = str(response).strip() if response else ""
        if response_str and len(response_str) > 0:
            return ModelEndpointTest(
                name="granite",
                status="success",
                response_time=response_time,
                response=response_str
            )
        else:
            return ModelEndpointTest(
                name="granite",
                status="error",
                response_time=response_time,
                error="Empty response received"
            )
            
    except GraniteAPIError as e:
        response_time = time.time() - start_time
        return ModelEndpointTest(
            name="granite",
            status="error",
            response_time=response_time,
            error=f"Granite API Error: {str(e)}"
        )
    except Exception as e:
        response_time = time.time() - start_time
        return ModelEndpointTest(
            name="granite",
            status="error",
            response_time=response_time,
            error=f"Unexpected error: {str(e)}"
        )


def test_json_capability() -> ModelEndpointTest:
    """Test JSON response capability required for classification and questionnaires."""
    prompts = _load_preflight_prompts()
    test_prompt = prompts["json_capability"]
    
    start_time = time.time()
    try:
        # Test with Granite since it's our primary model
        response = granite_client.call_api(
            prompt=test_prompt,
            max_tokens=50,
            temperature=0.0,
            return_metadata=False
        )
        response_time = time.time() - start_time
        
        if response:
            # Try to parse as JSON
            import json
            try:
                # Extract just the JSON part if the response contains extra text
                if isinstance(response, str):
                    # Look for JSON content
                    if '{' in response and '}' in response:
                        json_start = response.index('{')
                        json_end = response.rindex('}') + 1
                        json_str = response[json_start:json_end]
                        parsed = json.loads(json_str)
                    else:
                        raise ValueError("No JSON found in response")
                else:
                    parsed = json.loads(response)
                    
                return ModelEndpointTest(
                    name="json_capability",
                    status="success",
                    response_time=response_time,
                    response=f"JSON: {str(parsed)}"
                )
            except (json.JSONDecodeError, ValueError) as e:
                return ModelEndpointTest(
                    name="json_capability",
                    status="warning",
                    response_time=response_time,
                    error=f"JSON parsing warning: {str(e)}",
                    response=str(response)[:100]
                )
        else:
            return ModelEndpointTest(
                name="json_capability",
                status="error",
                response_time=response_time,
                error="Empty response"
            )
            
    except Exception as e:
        response_time = time.time() - start_time
        return ModelEndpointTest(
            name="json_capability",
            status="error",
            response_time=response_time,
            error=f"Error testing JSON capability: {str(e)}"
        )


@handle_node_errors
def preflight_check(state: ContractAnalysisState) -> Dict[str, Any]:
    """
    Perform preflight checks to verify model endpoint connectivity.
    
    Args:
        state: The current workflow state
        
    Returns:
        Updated state with preflight results
    """
    print("\n=== PREFLIGHT CHECKS ===")
    print("Testing model endpoint connectivity...")
    
    # Determine which models to test based on configuration
    required_models = []
    required_models.append('granite')  # Always test Granite
    
    print(f"Required models: {', '.join(required_models)}")
    
    test_results: List[ModelEndpointTest] = []
    total_start = time.time()
    
    # Test Granite endpoint
    if 'granite' in required_models:
        print("Testing Granite endpoint...")
        granite_test = test_granite_endpoint()
        test_results.append(granite_test)
        status_emoji = "✓" if granite_test.status == "success" else "✗"
        print(f"  {status_emoji} Granite: {granite_test.status} ({granite_test.response_time:.2f}s)")
        
        # Also test JSON capability with Granite
        json_test = test_json_capability()
        test_results.append(json_test)
        if json_test.status == "success":
            print("  ✓ JSON capability: verified")
        elif json_test.status == "warning":
            print(f"  ⚠ JSON capability: {json_test.error}")
        else:
            print(f"  ✗ JSON capability: {json_test.error}")
    
    total_time = time.time() - total_start
    
    # Analyze results
    successful_models = [t.name for t in test_results if t.status == "success"]
    failed_models = [t.name for t in test_results if t.status == "error"]
    warning_models = [t.name for t in test_results if t.status == "warning"]
    
    # Determine overall success
    # We need at least Granite to be successful
    granite_ok = any(t.name == "granite" and t.status == "success" for t in test_results)
    overall_success = granite_ok
    
    # Create summary
    print("\n=== PREFLIGHT SUMMARY ===")
    if successful_models:
        # Don't count json_capability in the model count
        model_count = len([m for m in successful_models if m != "json_capability"])
        total_count = len([m for m in required_models])
        print(f"✓ Successful: {model_count}/{total_count} models")
    if warning_models:
        print(f"⚠ Warnings: {', '.join(warning_models)}")
    if failed_models:
        print(f"✗ Failed: {', '.join(failed_models)}")
    
    # Build preflight results
    preflight_results = {
        'timestamp': datetime.now().isoformat(),
        'overall_success': overall_success,
        'required_models': required_models,
        'test_results': [t.to_dict() for t in test_results],
        'successful_models': successful_models,
        'failed_models': failed_models,
        'total_response_time': total_time,
        'config_used': {
            'primary_model': 'granite'
        }
    }
    
    # Update state
    state['preflight_results'] = preflight_results
    
    if overall_success:
        print(f"\n✅ PREFLIGHT PASSED - All {len(successful_models)} model(s) accessible")
        print("Proceeding with workflow...")
    else:
        print("\n❌ PREFLIGHT FAILED - Required model endpoints are not accessible")
        if failed_models:
            print("Failed models:")
            for test in test_results:
                if test.status == "error":
                    print(f"  - {test.name}: {test.error}")
        raise RuntimeError("Preflight checks failed. Please check model configurations and try again.")
    
    return state