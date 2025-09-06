#!/usr/bin/env python3
"""
Test Granite 3.3 function calling capabilities
"""

import os
import json
from utils.granite_client import GraniteClient

# Set up environment
os.environ['FORCE_GRANITE'] = 'true'

def test_function_calling():
    """Test if Granite 3.3 supports function calling"""
    
    client = GraniteClient()
    print(f"Testing model: {client.model_name}")
    print(f"API endpoint: {client.api_url}\n")
    
    # Define a function/tool for rule evaluation
    tools = [
        {
            "type": "function",
            "function": {
                "name": "evaluate_rule_compliance",
                "description": "Evaluate whether a document complies with a specific rule",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "status": {
                            "type": "string",
                            "enum": ["compliant", "non_compliant", "partially_compliant", "not_applicable", "requires_review"],
                            "description": "The compliance status"
                        },
                        "confidence": {
                            "type": "number",
                            "description": "Confidence score between 0 and 1",
                            "minimum": 0,
                            "maximum": 1
                        },
                        "rationale": {
                            "type": "string",
                            "description": "Explanation of the compliance determination"
                        },
                        "specific_issues": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of specific non-compliance issues"
                        },
                        "evidence_quotes": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Relevant quotes from the document"
                        }
                    },
                    "required": ["status", "confidence", "rationale"]
                }
            }
        }
    ]
    
    # Test prompt
    prompt = """Evaluate whether this document complies with the following rule:

Rule: Software must include at least 1 year warranty
Document Text: The software is provided with a 90-day warranty period.

Please evaluate the compliance using the evaluate_rule_compliance function."""

    print("=" * 60)
    print("TEST 1: Function Calling with tools parameter")
    print("=" * 60)
    
    try:
        # Test with tools parameter
        response = client.call_api(
            prompt,
            temperature=0.1,
            max_tokens=500,
            tools=tools,
            tool_choice="auto"
        )
        
        print("Response:", json.dumps(response, indent=2) if isinstance(response, dict) else response)
        
    except Exception as e:
        print(f"❌ Function calling with tools failed: {e}")
    
    print("\n" + "=" * 60)
    print("TEST 2: Function calling with functions parameter (legacy)")
    print("=" * 60)
    
    try:
        # Test with legacy functions parameter
        response = client.call_api(
            prompt,
            temperature=0.1,
            max_tokens=500,
            functions=[tools[0]["function"]],
            function_call="auto"
        )
        
        print("Response:", json.dumps(response, indent=2) if isinstance(response, dict) else response)
        
    except Exception as e:
        print(f"❌ Function calling with functions failed: {e}")
    
    print("\n" + "=" * 60)
    print("TEST 3: System message with function instructions")
    print("=" * 60)
    
    system_message = """You are a rule compliance evaluator. When evaluating rules, respond with a JSON object containing:
- status: one of [compliant, non_compliant, partially_compliant, not_applicable, requires_review]
- confidence: a number between 0 and 1
- rationale: explanation of your determination
- specific_issues: array of specific issues found (if any)
- evidence_quotes: relevant quotes from the document

Respond ONLY with the JSON object, no additional text."""
    
    try:
        response = client.call_api_with_system_message(
            system_message,
            prompt,
            temperature=0.1,
            max_tokens=500
        )
        
        print("Response:", response)
        
        # Try to parse as JSON
        try:
            parsed = json.loads(response)
            print("\n✅ Successfully parsed as JSON:")
            print(json.dumps(parsed, indent=2))
        except json.JSONDecodeError:
            print("\n⚠️ Response is not valid JSON")
            
    except Exception as e:
        print(f"❌ System message approach failed: {e}")
    
    print("\n" + "=" * 60)
    print("TEST 4: Streaming with system message")
    print("=" * 60)
    
    try:
        print("Streaming response:")
        accumulated = ""
        
        def stream_callback(chunk, metadata):
            nonlocal accumulated
            accumulated += chunk
            print(chunk, end="", flush=True)
        
        response = client.call_api(
            prompt,
            temperature=0.1,
            max_tokens=500,
            stream=True,
            stream_callback=stream_callback
        )
        
        print("\n\nFull accumulated response:")
        print(accumulated)
        
    except Exception as e:
        print(f"❌ Streaming failed: {e}")
    
    print("\n" + "=" * 60)
    print("TEST 5: Tool use with streaming")
    print("=" * 60)
    
    try:
        print("Testing streaming with tools...")
        accumulated = ""
        
        def stream_callback(chunk, metadata):
            nonlocal accumulated
            accumulated += chunk
            print(chunk, end="", flush=True)
        
        response = client.call_api(
            prompt,
            temperature=0.1,
            max_tokens=500,
            tools=tools,
            tool_choice="auto",
            stream=True,
            stream_callback=stream_callback
        )
        
        print("\n\nFull response:", response)
        
    except Exception as e:
        print(f"❌ Streaming with tools failed: {e}")


if __name__ == "__main__":
    test_function_calling()