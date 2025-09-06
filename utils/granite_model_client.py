"""
Enhanced Granite Model Client Implementation
Extends ModelClient abstraction for Granite 3.3 and other Granite models
"""

import os
import time
from typing import Dict, List, Optional, Any, Tuple
import requests

from utils.model_client import ModelClient, ModelResponse, ModelConfig
from utils.granite_client import (
    retry_with_exponential_backoff,
    GraniteRateLimitError,
    GraniteServerError
)


class GraniteModelClient(ModelClient):
    """Enhanced Granite client implementing ModelClient interface"""
    
    def __init__(self, config: ModelConfig):
        """Initialize Granite client with configuration"""
        super().__init__(config)
        
        # Set up endpoint - support both old and new env vars
        self.endpoint = (
            config.endpoint or 
            os.getenv('GRANITE_API_URL') or 
            os.getenv('GRANITE_URL', 'http://localhost:8000')
        )
        
        self.api_key = config.api_key or os.getenv('GRANITE_API_KEY', '')
        
        # Session for connection pooling
        self.session = requests.Session()
        if self.api_key:
            self.session.headers.update({
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json'
            })
    
    @retry_with_exponential_backoff(max_retries=3)
    def _make_api_call(self, endpoint: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Make API call with retry logic"""
        response = self.session.post(
            endpoint,
            json=payload,
            timeout=self.config.timeout
        )
        
        if response.status_code == 429:
            raise GraniteRateLimitError("Rate limit exceeded")
        elif response.status_code >= 500:
            raise GraniteServerError(f"Server error: {response.status_code}")
        
        response.raise_for_status()
        return response.json()
    
    def generate(self, prompt: str, **kwargs) -> ModelResponse:
        """
        Generate a response from Granite model
        
        Args:
            prompt: The input prompt
            **kwargs: Additional parameters
            
        Returns:
            ModelResponse with the generated content
        """
        # Merge kwargs with config
        temperature = kwargs.get('temperature', self.config.temperature)
        max_tokens = kwargs.get('max_tokens', self.config.max_tokens)
        top_p = kwargs.get('top_p', self.config.top_p)
        
        # Build request payload
        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "top_p": top_p,
            "frequency_penalty": self.config.frequency_penalty,
            "presence_penalty": self.config.presence_penalty,
            "stream": False,
            "logprobs": True,
            "top_logprobs": 5
        }
        
        # Add additional params if provided
        if self.config.additional_params:
            payload.update(self.config.additional_params)
        
        try:
            # Make API call with retry
            data = self._make_api_call(
                f"{self.endpoint}/v1/completions",
                payload
            )
            
            # Extract response data
            choice = data.get('choices', [{}])[0]
            content = choice.get('text', '')
            
            # Extract logprobs for confidence
            logprobs = None
            logprobs_data = choice.get('logprobs', {})
            if logprobs_data and 'token_logprobs' in logprobs_data:
                logprobs = logprobs_data['token_logprobs']
            
            # Build response
            response = ModelResponse(
                content=content.strip(),
                model=data.get('model', self.model_name),
                tokens_used=data.get('usage', {}).get('total_tokens', 0),
                logprobs=logprobs,
                metadata={
                    'finish_reason': choice.get('finish_reason'),
                    'usage': data.get('usage', {}),
                    'response_time': time.time()
                },
                raw_response=data
            )
            
            # Calculate confidence
            response.confidence = self.extract_confidence(response)
            
            return response
            
        except Exception as e:
            print(f"Granite generation error: {str(e)}")
            return ModelResponse(
                content="",
                model=self.model_name,
                tokens_used=0,
                confidence=0.0,
                metadata={'error': str(e)}
            )
    
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
        # Format prompt with schema
        formatted_prompt = self.format_prompt_with_schema(prompt, schema)
        
        # Get retry count
        max_retries = kwargs.get('schema_retries', 3)
        last_error = None
        
        for attempt in range(max_retries):
            # Add error feedback after first attempt
            if attempt > 0 and last_error:
                formatted_prompt = f"""{formatted_prompt}

Previous attempt failed: {last_error}
Please ensure your response is valid JSON matching the schema."""
            
            response = self.generate(formatted_prompt, **kwargs)
            
            if response.content:
                # Try to extract JSON from response
                content = response.content
                
                # Handle common issues
                if "```json" in content:
                    # Extract JSON from markdown code block
                    start = content.find("```json") + 7
                    end = content.find("```", start)
                    if end > start:
                        content = content[start:end].strip()
                
                # Validate JSON
                is_valid, parsed_json, error = self.validate_json_response(content, schema)
                
                if is_valid:
                    return response, parsed_json
                
                last_error = error
        
        # Failed after retries
        return response, {}
    
    def batch_generate(self, prompts: List[str], **kwargs) -> List[ModelResponse]:
        """
        Generate responses for multiple prompts
        
        Args:
            prompts: List of input prompts
            **kwargs: Additional parameters
            
        Returns:
            List of ModelResponses
        """
        responses = []
        batch_size = kwargs.get('batch_size', 5)
        
        for i in range(0, len(prompts), batch_size):
            batch = prompts[i:i+batch_size]
            
            for prompt in batch:
                response = self.generate(prompt, **kwargs)
                responses.append(response)
            
            # Delay between batches to avoid rate limiting
            if i + batch_size < len(prompts):
                time.sleep(0.5)
        
        return responses
    
    def is_available(self) -> bool:
        """
        Check if Granite API is available
        
        Returns:
            True if API is accessible, False otherwise
        """
        try:
            response = self.session.get(
                f"{self.endpoint}/v1/models",
                timeout=5
            )
            return response.status_code == 200
        except Exception as e:
            print(f"Granite availability check failed: {str(e)}")
            return False
    
    def generate_embedding(self, text: str) -> Optional[List[float]]:
        """
        Generate embeddings using Granite embedding model
        
        Args:
            text: Text to embed
            
        Returns:
            Embedding vector or None if not available
        """
        embedding_url = os.getenv('GRANITE_EMBEDDING_URL')
        if not embedding_url:
            return None
        
        try:
            payload = {
                "model": "granite-embedding-125m",
                "input": text
            }
            
            data = self._make_api_call(
                f"{embedding_url}/v1/embeddings",
                payload
            )
            
            return data.get('data', [{}])[0].get('embedding')
            
        except Exception as e:
            print(f"Embedding generation failed: {str(e)}")
            return None
    
    def __repr__(self) -> str:
        return f"GraniteModelClient(model={self.model_name}, endpoint={self.endpoint})"