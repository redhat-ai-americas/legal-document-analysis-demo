"""
Shared classification utilities for sentence classification nodes.

This module provides common functionality used across both target and reference
sentence classification to eliminate code duplication.
"""

import yaml
import json
import re
import os
import hashlib
from typing import Dict, List, Any, Tuple, Optional, Union
from utils.granite_client import granite_client, GraniteAPIError

# Simple in-memory cache for classification results
_classification_cache = {}

def load_terminology_yaml(path: str) -> List[Dict[str, Any]]:
    """Load terminology definitions from YAML file."""
    with open(path, 'r') as f:
        terminology_data = yaml.safe_load(f)
    return terminology_data

def load_prompt_template(template_name: str = "classifier.yaml") -> Dict[str, Any]:
    """Load classification prompt template from YAML file."""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    # If template_name doesn't end with .yaml, append it
    if not template_name.endswith('.yaml'):
        template_name = f"{template_name}.yaml"
    prompt_path = os.path.join(base_dir, "prompts", template_name)
    with open(prompt_path, 'r') as f:
        return yaml.safe_load(f)

def format_terminology_for_prompt(terminology_data: List[Dict[str, Any]], include_examples: bool = True) -> str:
    """Format terminology data for inclusion in prompts."""
    formatted_terms = []
    for item in terminology_data:
        term_name = item.get('name', '')
        definition = item.get('definition', '')
        examples = item.get('examples', [])
        
        if term_name and definition:
            term_str = f"Term: {term_name}\nDefinition: {definition}"
            if include_examples and examples:
                term_str += "\nExamples:\n" + "\n".join(f"- {example}" for example in examples)
            formatted_terms.append(term_str)
    
    return "\n\n".join(formatted_terms)

def extract_term_from_classification(classification_result: Union[str, Dict[str, Any]]) -> Tuple[str, float]:
    """
    Extract term and confidence from classification result with fallback logic.
    
    Args:
        classification_result: Raw response from classification model
        
    Returns:
        Tuple of (term, confidence_score)
    """
    try:
        # If already a dict, use it directly
        if isinstance(classification_result, dict):
            term = classification_result.get('term', '')
            confidence = classification_result.get('confidence', 0.5)
            return term.strip().strip('"').strip("'"), float(confidence) if isinstance(confidence, (int, float)) else 0.5
            
        # Try to parse as JSON
        result_json = json.loads(classification_result)
        term = result_json.get('term', '')
        confidence = result_json.get('confidence', 0.5)
        
        # Clean up the term
        term = term.strip().strip('"').strip("'")
        
        return term, float(confidence) if isinstance(confidence, (int, float)) else 0.5
        
    except json.JSONDecodeError:
        # Fallback: Try to extract term from text response
        term = ""
        confidence = 0.3  # Lower confidence for fallback parsing
        
        # Look for common patterns
        patterns = [
            r'"term":\s*"([^"]+)"',
            r"'term':\s*'([^']+)'",
            r'term:\s*([^\n,}]+)',
            r'Term:\s*([^\n,}]+)',
            r'TERM:\s*([^\n,}]+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, str(classification_result), re.IGNORECASE)
            if match:
                term = match.group(1).strip()
                break
        
        # If no pattern found, use the whole response (cleaned)
        if not term:
            term = str(classification_result).strip()
            if len(term) > 50:  # Probably not a valid term
                term = ""
        
        return term, confidence

def create_cache_key(sentence: str, terminology_hash: str) -> str:
    """Create a cache key for classification results."""
    content = f"{sentence}_{terminology_hash}"
    return hashlib.md5(content.encode()).hexdigest()

def get_terminology_hash(terminology_data: List[Dict[str, Any]]) -> str:
    """Generate a hash of terminology data for cache key generation."""
    # Create a simple hash based on term names and definitions
    content = ""
    for item in terminology_data:
        # Support both old and new data structures
        term_name = item.get('name', item.get('term', ''))
        term_definition = item.get('definition', item.get('project_specific_definition', ''))
        content += f"{term_name}_{term_definition}"
    return hashlib.md5(content.encode()).hexdigest()

def get_cached_classification(sentence: str, terminology_hash: str) -> Optional[Dict[str, Any]]:
    """Retrieve cached classification result if available."""
    cache_key = create_cache_key(sentence, terminology_hash)
    return _classification_cache.get(cache_key)

def cache_classification_result(sentence: str, terminology_hash: str, result: Dict[str, Any]) -> None:
    """Cache a classification result."""
    cache_key = create_cache_key(sentence, terminology_hash)
    _classification_cache[cache_key] = result

def clear_classification_cache() -> None:
    """Clear the classification cache."""
    global _classification_cache
    _classification_cache = {}

def get_cache_stats() -> Dict[str, int]:
    """Get cache statistics."""
    return {
        "total_entries": len(_classification_cache),
        "memory_usage_bytes": sum(len(str(k)) + len(str(v)) for k, v in _classification_cache.items())
    }

def classify_sentence_with_granite(
    sentence: str, 
    terminology_data: List[Dict[str, Any]], 
    template_data: Dict[str, Any],
    use_cache: bool = True,
    include_examples: bool = True
) -> Dict[str, Any]:
    """
    Classify a single sentence using Granite model with caching support.
    
    Args:
        sentence: Sentence to classify
        terminology_data: List of terminology definitions
        template_data: Prompt template data
        use_cache: Whether to use caching
        include_examples: Whether to include examples in the prompt
        
    Returns:
        Classification result dictionary
    """
    # Generate terminology hash for caching
    terminology_hash = get_terminology_hash(terminology_data)
    
    # Check cache first
    if use_cache:
        cached_result = get_cached_classification(sentence, terminology_hash)
        if cached_result:
            return cached_result
    
    try:
        # Format terminology for prompt
        classes_formatted = format_terminology_for_prompt(terminology_data, include_examples)
        
        # Create prompt from template
        prompt = template_data['template'].format(
            document=sentence,
            classes=classes_formatted
        )
        
        # Call Granite API
        classification_result = granite_client.call_api(
            prompt=prompt,
            temperature=0.0,
            max_tokens=50
        )
        
        # Extract term and confidence
        term, confidence = extract_term_from_classification(classification_result)
        
        # Prepare result
        result = {
            "sentence": sentence,
            "classification_result": classification_result,
            "term": term,
            "confidence": confidence,
            "raw_response": classification_result
        }
        
        # Cache the result
        if use_cache:
            cache_classification_result(sentence, terminology_hash, result)
        
        return result
        
    except GraniteAPIError as e:
        # Return error result
        result = {
            "sentence": sentence,
            "classification_result": "",
            "term": "",
            "confidence": 0.0,
            "error": str(e),
            "raw_response": ""
        }
        
        return result

def validate_classification_batch(
    classifications: List[Dict[str, Any]], 
    terminology_data: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Validate a batch of classifications and add validation metadata.
    
    Args:
        classifications: List of classification results
        terminology_data: List of terminology definitions
        
    Returns:
        Classifications enhanced with validation data
    """
    # Create a lookup of valid terms
    valid_terms = {item['term'] for item in terminology_data}
    
    enhanced_classifications = []
    
    for classification in classifications:
        term = classification.get('term', '')
        confidence = classification.get('confidence', 0.0)
        
        # Validation checks
        is_valid_term = term in valid_terms
        is_high_confidence = confidence >= 0.7
        is_medium_confidence = 0.4 <= confidence < 0.7
        needs_review = not is_valid_term or confidence < 0.4
        
        # Add validation metadata
        enhanced_classification = classification.copy()
        enhanced_classification.update({
            'is_valid_term': is_valid_term,
            'confidence_level': 'high' if is_high_confidence else 'medium' if is_medium_confidence else 'low',
            'needs_manual_review': needs_review,
            'validation_notes': []
        })
        
        # Add specific validation notes
        if not is_valid_term and term:
            enhanced_classification['validation_notes'].append(f"Unknown term: {term}")
        if confidence < 0.4:
            enhanced_classification['validation_notes'].append("Low confidence classification")
        
        enhanced_classifications.append(enhanced_classification)
    
    return enhanced_classifications