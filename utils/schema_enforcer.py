"""
Schema Enforcement with Retries
Ensures LLM outputs conform to required JSON schemas
"""

import json
import time
from typing import Dict, Any, Optional, List
from enum import Enum
from dataclasses import dataclass
from jsonschema import validate, ValidationError

from utils.model_client import ModelClient
from utils.feature_flags import is_feature_enabled


class RetryStrategy(Enum):
    """Retry strategies for schema enforcement"""
    EXPONENTIAL = "exponential"
    LINEAR = "linear"
    IMMEDIATE = "immediate"


@dataclass
class SchemaValidationResult:
    """Result of schema validation"""
    is_valid: bool
    data: Optional[Dict[str, Any]] = None
    errors: List[str] = None
    attempt: int = 1
    
    def __post_init__(self):
        if self.errors is None:
            self.errors = []


class SchemaEnforcer:
    """Enforces JSON schema compliance with intelligent retries"""
    
    def __init__(
        self,
        max_retries: int = 3,
        retry_strategy: RetryStrategy = RetryStrategy.EXPONENTIAL,
        base_delay: float = 1.0,
        strict_mode: bool = True
    ):
        """
        Initialize schema enforcer
        
        Args:
            max_retries: Maximum retry attempts
            retry_strategy: Strategy for retry delays
            base_delay: Base delay between retries
            strict_mode: Whether to enforce strict validation
        """
        self.max_retries = max_retries
        self.retry_strategy = retry_strategy
        self.base_delay = base_delay
        self.strict_mode = strict_mode
    
    def enforce_schema(
        self,
        model_client: ModelClient,
        prompt: str,
        schema: Dict[str, Any],
        **generation_kwargs
    ) -> SchemaValidationResult:
        """
        Generate response with schema enforcement
        
        Args:
            model_client: Model client to use
            prompt: Generation prompt
            schema: JSON schema to enforce
            **generation_kwargs: Additional generation parameters
            
        Returns:
            SchemaValidationResult with validated data
        """
        if not is_feature_enabled('strict_json_schemas'):
            # Feature disabled, use simple generation
            return self._simple_generation(model_client, prompt, schema, **generation_kwargs)
        
        # Initial prompt with schema
        current_prompt = self._format_prompt_with_schema(prompt, schema)
        errors_history = []
        
        for attempt in range(1, self.max_retries + 1):
            # Add error feedback after first attempt
            if attempt > 1:
                current_prompt = self._add_error_feedback(
                    prompt, schema, errors_history
                )
            
            # Generate response
            response = model_client.generate(current_prompt, **generation_kwargs)
            
            # Extract and validate JSON
            result = self._extract_and_validate(response.content, schema)
            
            if result.is_valid:
                result.attempt = attempt
                return result
            
            # Record errors
            errors_history.extend(result.errors)
            
            # Wait before retry
            if attempt < self.max_retries:
                self._wait_before_retry(attempt)
        
        # All retries exhausted
        return SchemaValidationResult(
            is_valid=False,
            errors=errors_history,
            attempt=self.max_retries
        )
    
    def validate_json(
        self,
        data: Any,
        schema: Dict[str, Any]
    ) -> SchemaValidationResult:
        """
        Validate JSON data against schema
        
        Args:
            data: Data to validate
            schema: JSON schema
            
        Returns:
            ValidationResult
        """
        try:
            validate(instance=data, schema=schema)
            return SchemaValidationResult(
                is_valid=True,
                data=data
            )
        except ValidationError as e:
            return SchemaValidationResult(
                is_valid=False,
                errors=[str(e)]
            )
    
    def _simple_generation(
        self,
        model_client: ModelClient,
        prompt: str,
        schema: Dict[str, Any],
        **kwargs
    ) -> SchemaValidationResult:
        """Simple generation without strict enforcement"""
        response, parsed = model_client.generate_with_schema(
            prompt, schema, **kwargs
        )
        
        if parsed:
            return SchemaValidationResult(
                is_valid=True,
                data=parsed
            )
        else:
            return SchemaValidationResult(
                is_valid=False,
                errors=["Failed to parse JSON"]
            )
    
    def _format_prompt_with_schema(
        self,
        prompt: str,
        schema: Dict[str, Any]
    ) -> str:
        """Format prompt with schema requirements"""
        schema_str = json.dumps(schema, indent=2)
        
        # Extract required fields for emphasis
        required_fields = schema.get('required', [])
        properties = schema.get('properties', {})
        
        field_descriptions = []
        for field in required_fields:
            if field in properties:
                field_type = properties[field].get('type', 'any')
                field_descriptions.append(f"- {field} ({field_type}): required")
        
        fields_str = '\n'.join(field_descriptions)
        
        return f"""{prompt}

You MUST respond with valid JSON that conforms to this schema:
```json
{schema_str}
```

Required fields:
{fields_str}

IMPORTANT:
1. Response must be valid JSON only
2. No additional text or explanations
3. All required fields must be present
4. Field types must match the schema exactly"""
    
    def _add_error_feedback(
        self,
        original_prompt: str,
        schema: Dict[str, Any],
        errors: List[str]
    ) -> str:
        """Add error feedback to prompt for retry"""
        error_summary = self._summarize_errors(errors)
        
        return f"""{self._format_prompt_with_schema(original_prompt, schema)}

PREVIOUS ATTEMPTS FAILED WITH ERRORS:
{error_summary}

Please fix these specific issues:
{self._get_fix_instructions(errors, schema)}

Respond with corrected JSON that addresses all errors."""
    
    def _extract_and_validate(
        self,
        content: str,
        schema: Dict[str, Any]
    ) -> SchemaValidationResult:
        """Extract JSON from content and validate"""
        # Try to extract JSON from response
        json_str = self._extract_json(content)
        
        if not json_str:
            return SchemaValidationResult(
                is_valid=False,
                errors=["No valid JSON found in response"]
            )
        
        # Parse JSON
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            return SchemaValidationResult(
                is_valid=False,
                errors=[f"JSON parse error: {str(e)}"]
            )
        
        # Validate against schema
        return self.validate_json(data, schema)
    
    def _extract_json(self, content: str) -> Optional[str]:
        """Extract JSON from potentially messy content"""
        # Remove markdown code blocks
        if "```json" in content:
            start = content.find("```json") + 7
            end = content.find("```", start)
            if end > start:
                content = content[start:end].strip()
        elif "```" in content:
            start = content.find("```") + 3
            end = content.find("```", start)
            if end > start:
                content = content[start:end].strip()
        
        # Try to find JSON object or array
        content = content.strip()
        
        # Look for JSON start/end
        if content.startswith('{') or content.startswith('['):
            # Find matching close
            depth = 0
            in_string = False
            escape = False
            
            for i, char in enumerate(content):
                if escape:
                    escape = False
                    continue
                
                if char == '\\':
                    escape = True
                    continue
                
                if char == '"' and not escape:
                    in_string = not in_string
                    continue
                
                if not in_string:
                    if char in '{[':
                        depth += 1
                    elif char in '}]':
                        depth -= 1
                        if depth == 0:
                            return content[:i+1]
        
        return content if content else None
    
    def _summarize_errors(self, errors: List[str]) -> str:
        """Summarize errors for feedback"""
        if not errors:
            return "No specific errors"
        
        # Group similar errors
        unique_errors = []
        for error in errors:
            if error not in unique_errors:
                unique_errors.append(error)
        
        # Limit to most recent/relevant
        relevant_errors = unique_errors[-3:]
        
        return '\n'.join(f"- {error}" for error in relevant_errors)
    
    def _get_fix_instructions(
        self,
        errors: List[str],
        schema: Dict[str, Any]
    ) -> str:
        """Generate specific fix instructions from errors"""
        instructions = []
        
        for error in errors:
            if "required" in error.lower():
                # Missing required field
                instructions.append("Include all required fields")
            elif "type" in error.lower():
                # Type mismatch
                instructions.append("Ensure field types match schema")
            elif "parse" in error.lower():
                # JSON parse error
                instructions.append("Ensure response is valid JSON with proper quotes and brackets")
        
        # Add specific field requirements
        if 'required' in schema:
            instructions.append(f"Must include: {', '.join(schema['required'])}")
        
        return '\n'.join(set(instructions))  # Remove duplicates
    
    def _wait_before_retry(self, attempt: int):
        """Wait before retry based on strategy"""
        if self.retry_strategy == RetryStrategy.EXPONENTIAL:
            delay = self.base_delay * (2 ** (attempt - 1))
        elif self.retry_strategy == RetryStrategy.LINEAR:
            delay = self.base_delay * attempt
        else:  # IMMEDIATE
            delay = 0
        
        if delay > 0:
            time.sleep(min(delay, 10))  # Cap at 10 seconds


class SchemaLibrary:
    """Library of common schemas for reuse"""
    
    # Multi-label classification schema
    MULTI_LABEL_CLASSIFICATION = {
        "type": "object",
        "required": ["sentence", "labels"],
        "properties": {
            "sentence": {"type": "string"},
            "labels": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["label", "confidence"],
                    "properties": {
                        "label": {"type": "string"},
                        "confidence": {
                            "type": "number",
                            "minimum": 0,
                            "maximum": 1
                        },
                        "evidence": {"type": "string"}
                    }
                }
            }
        }
    }
    
    # Rule evaluation schema
    RULE_EVALUATION = {
        "type": "object",
        "required": ["rule_id", "status", "rationale"],
        "properties": {
            "rule_id": {"type": "string"},
            "status": {
                "type": "string",
                "enum": ["compliant", "non_compliant", "not_applicable", "unknown"]
            },
            "rationale": {"type": "string"},
            "citations": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["quote", "page"],
                    "properties": {
                        "quote": {"type": "string"},
                        "page": {"type": "integer"}
                    }
                }
            },
            "confidence": {
                "type": "number",
                "minimum": 0,
                "maximum": 1
            }
        }
    }
    
    # Entity extraction schema
    ENTITY_EXTRACTION = {
        "type": "object",
        "properties": {
            "parties": {
                "type": "array",
                "items": {"type": "string"}
            },
            "dates": {
                "type": "object",
                "properties": {
                    "effective_date": {"type": "string"},
                    "expiration_date": {"type": "string"},
                    "other_dates": {
                        "type": "array",
                        "items": {"type": "string"}
                    }
                }
            },
            "monetary_amounts": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "amount": {"type": "number"},
                        "currency": {"type": "string"},
                        "context": {"type": "string"}
                    }
                }
            }
        }
    }


# Global instance
schema_enforcer = SchemaEnforcer()


# Convenience functions
def enforce_schema(
    model_client: ModelClient,
    prompt: str,
    schema: Dict[str, Any],
    **kwargs
) -> SchemaValidationResult:
    """Enforce schema on model generation"""
    return schema_enforcer.enforce_schema(model_client, prompt, schema, **kwargs)


def validate_against_schema(data: Any, schema: Dict[str, Any]) -> SchemaValidationResult:
    """Validate data against schema"""
    return schema_enforcer.validate_json(data, schema)