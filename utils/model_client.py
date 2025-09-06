"""
Abstract Model Client Interface
Provides a unified interface for interacting with different LLM providers
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
import json


@dataclass
class ModelResponse:
    """Standardized response from any model client"""
    content: str
    model: str
    tokens_used: int
    confidence: Optional[float] = None
    logprobs: Optional[List[float]] = None
    metadata: Optional[Dict[str, Any]] = None
    raw_response: Optional[Any] = None


@dataclass
class ModelConfig:
    """Configuration for a model client"""
    model_name: str
    temperature: float = 0.1
    max_tokens: int = 2000
    top_p: float = 0.95
    frequency_penalty: float = 0.0
    presence_penalty: float = 0.0
    timeout: int = 30
    retry_attempts: int = 3
    api_key: Optional[str] = None
    endpoint: Optional[str] = None
    additional_params: Optional[Dict[str, Any]] = None


class ModelClient(ABC):
    """Abstract base class for all model clients"""
    
    def __init__(self, config: ModelConfig):
        """Initialize the model client with configuration"""
        self.config = config
        self.model_name = config.model_name
        
    @abstractmethod
    def generate(self, prompt: str, **kwargs) -> ModelResponse:
        """
        Generate a response from the model
        
        Args:
            prompt: The input prompt
            **kwargs: Additional model-specific parameters
            
        Returns:
            ModelResponse with the generated content
        """
        pass
    
    @abstractmethod
    def generate_with_schema(self, prompt: str, schema: Dict[str, Any], **kwargs) -> Tuple[ModelResponse, Dict]:
        """
        Generate a response that conforms to a JSON schema
        
        Args:
            prompt: The input prompt
            schema: JSON schema to enforce
            **kwargs: Additional parameters
            
        Returns:
            Tuple of (ModelResponse, parsed_json)
        """
        pass
    
    @abstractmethod
    def batch_generate(self, prompts: List[str], **kwargs) -> List[ModelResponse]:
        """
        Generate responses for multiple prompts
        
        Args:
            prompts: List of input prompts
            **kwargs: Additional parameters
            
        Returns:
            List of ModelResponses
        """
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """
        Check if the model is available and accessible
        
        Returns:
            True if model is available, False otherwise
        """
        pass
    
    def extract_confidence(self, response: ModelResponse) -> float:
        """
        Extract confidence score from model response
        Default implementation uses logprobs if available
        
        Args:
            response: The model response
            
        Returns:
            Confidence score between 0 and 1
        """
        if response.logprobs:
            # Convert logprobs to probability and average
            import math
            probs = [math.exp(lp) for lp in response.logprobs[:10]]  # Use first 10 tokens
            return sum(probs) / len(probs) if probs else 0.5
        return 0.5  # Default confidence if no logprobs
    
    def validate_json_response(self, content: str, schema: Dict[str, Any]) -> Tuple[bool, Optional[Dict], Optional[str]]:
        """
        Validate JSON response against schema
        
        Args:
            content: JSON string to validate
            schema: JSON schema to validate against
            
        Returns:
            Tuple of (is_valid, parsed_json, error_message)
        """
        try:
            parsed = json.loads(content)
            
            # Basic schema validation (can be enhanced with jsonschema library)
            if schema:
                required_fields = schema.get('required', [])
                properties = schema.get('properties', {})
                
                for field in required_fields:
                    if field not in parsed:
                        return False, None, f"Missing required field: {field}"
                
                for field, value in parsed.items():
                    if field in properties:
                        field_schema = properties[field]
                        field_type = field_schema.get('type')
                        
                        # Basic type checking
                        if field_type:
                            if field_type == 'string' and not isinstance(value, str):
                                return False, None, f"Field {field} should be string"
                            elif field_type == 'number' and not isinstance(value, (int, float)):
                                return False, None, f"Field {field} should be number"
                            elif field_type == 'array' and not isinstance(value, list):
                                return False, None, f"Field {field} should be array"
                            elif field_type == 'object' and not isinstance(value, dict):
                                return False, None, f"Field {field} should be object"
            
            return True, parsed, None
            
        except json.JSONDecodeError as e:
            return False, None, f"JSON parse error: {str(e)}"
        except Exception as e:
            return False, None, f"Validation error: {str(e)}"
    
    def format_prompt_with_schema(self, prompt: str, schema: Dict[str, Any]) -> str:
        """
        Format prompt to include schema requirements
        
        Args:
            prompt: Original prompt
            schema: JSON schema to include
            
        Returns:
            Formatted prompt with schema instructions
        """
        schema_str = json.dumps(schema, indent=2)
        return f"""{prompt}

You must respond with valid JSON that conforms to this schema:
```json
{schema_str}
```

Ensure your response is valid JSON only, with no additional text."""
    
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(model={self.model_name})"