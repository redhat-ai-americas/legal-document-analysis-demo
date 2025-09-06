"""
Local Model Client Implementation
Supports Ollama and other local model servers
"""

import os
import time
from typing import Dict, List, Optional, Any, Tuple
import requests

from utils.model_client import ModelClient, ModelResponse, ModelConfig


class LocalModelClient(ModelClient):
    """Client for interacting with local models (Ollama, llama.cpp, etc.)"""
    
    def __init__(self, config: ModelConfig):
        """Initialize local model client with configuration"""
        super().__init__(config)
        
        # Determine endpoint based on model type
        if 'ollama' in config.model_name.lower() or not config.endpoint:
            # Default to Ollama endpoint
            self.endpoint = config.endpoint or os.getenv('OLLAMA_URL', 'http://localhost:11434')
            self.is_ollama = True
        else:
            # Custom local model endpoint
            self.endpoint = config.endpoint
            self.is_ollama = False
        
        # Session for connection pooling
        self.session = requests.Session()
        self.session.headers.update({'Content-Type': 'application/json'})
    
    def generate(self, prompt: str, **kwargs) -> ModelResponse:
        """
        Generate a response from local model
        
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
        
        try:
            if self.is_ollama:
                # Ollama API format
                payload = {
                    "model": self.model_name,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": temperature,
                        "num_predict": max_tokens,
                        "top_p": top_p,
                    }
                }
                
                response = self.session.post(
                    f"{self.endpoint}/api/generate",
                    json=payload,
                    timeout=self.config.timeout
                )
                
                response.raise_for_status()
                data = response.json()
                
                # Extract Ollama response
                content = data.get('response', '')
                
                return ModelResponse(
                    content=content.strip(),
                    model=data.get('model', self.model_name),
                    tokens_used=data.get('eval_count', 0) + data.get('prompt_eval_count', 0),
                    confidence=0.85,  # Default confidence for local models
                    metadata={
                        'eval_duration': data.get('eval_duration'),
                        'total_duration': data.get('total_duration'),
                        'done': data.get('done', True)
                    },
                    raw_response=data
                )
            
            else:
                # Generic local model API (OpenAI-compatible)
                payload = {
                    "model": self.model_name,
                    "prompt": prompt,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    "top_p": top_p,
                    "stream": False
                }
                
                response = self.session.post(
                    f"{self.endpoint}/v1/completions",
                    json=payload,
                    timeout=self.config.timeout
                )
                
                response.raise_for_status()
                data = response.json()
                
                # Extract response
                choice = data.get('choices', [{}])[0]
                content = choice.get('text', '')
                
                return ModelResponse(
                    content=content.strip(),
                    model=data.get('model', self.model_name),
                    tokens_used=data.get('usage', {}).get('total_tokens', 0),
                    confidence=0.85,
                    metadata={
                        'finish_reason': choice.get('finish_reason'),
                        'usage': data.get('usage', {})
                    },
                    raw_response=data
                )
                
        except Exception as e:
            print(f"Local model error: {str(e)}")
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
        # Format prompt with schema and JSON mode instructions
        formatted_prompt = f"""{self.format_prompt_with_schema(prompt, schema)}

IMPORTANT: Respond ONLY with valid JSON. No explanations or additional text."""
        
        # For Ollama, we can use the format parameter for better JSON
        if self.is_ollama:
            kwargs['format'] = 'json'
        
        # Try to get valid JSON
        max_retries = kwargs.get('schema_retries', 3)
        last_error = None
        
        for attempt in range(max_retries):
            if attempt > 0 and last_error:
                formatted_prompt += f"\n\nPrevious error: {last_error}\nPlease fix and provide valid JSON."
            
            response = self.generate(formatted_prompt, **kwargs)
            
            if response.content:
                content = response.content
                
                # Clean up common issues
                if "```json" in content:
                    start = content.find("```json") + 7
                    end = content.find("```", start)
                    if end > start:
                        content = content[start:end].strip()
                
                # Validate
                is_valid, parsed_json, error = self.validate_json_response(content, schema)
                
                if is_valid:
                    return response, parsed_json
                
                last_error = error
        
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
        
        for prompt in prompts:
            response = self.generate(prompt, **kwargs)
            responses.append(response)
            
            # Small delay for local model stability
            time.sleep(0.1)
        
        return responses
    
    def is_available(self) -> bool:
        """
        Check if local model is available
        
        Returns:
            True if model is accessible, False otherwise
        """
        try:
            if self.is_ollama:
                # Check Ollama API
                response = self.session.get(
                    f"{self.endpoint}/api/tags",
                    timeout=5
                )
                
                if response.status_code == 200:
                    # Check if our model is in the list
                    data = response.json()
                    models = [m.get('name', '') for m in data.get('models', [])]
                    
                    # Handle model name variations (e.g., "llama3" vs "llama3:latest")
                    model_base = self.model_name.split(':')[0]
                    return any(model_base in m for m in models)
                
            else:
                # Generic health check
                response = self.session.get(
                    f"{self.endpoint}/v1/models",
                    timeout=5
                )
                return response.status_code == 200
                
        except Exception as e:
            print(f"Local model availability check failed: {str(e)}")
            
        return False
    
    def pull_model(self, model_name: Optional[str] = None) -> bool:
        """
        Pull/download a model (Ollama specific)
        
        Args:
            model_name: Model to pull, defaults to configured model
            
        Returns:
            True if successful, False otherwise
        """
        if not self.is_ollama:
            return False
        
        model = model_name or self.model_name
        
        try:
            print(f"Pulling model {model}...")
            response = self.session.post(
                f"{self.endpoint}/api/pull",
                json={"name": model},
                timeout=600  # 10 minutes for large models
            )
            
            if response.status_code == 200:
                print(f"Model {model} pulled successfully")
                return True
                
        except Exception as e:
            print(f"Failed to pull model: {str(e)}")
        
        return False
    
    def list_models(self) -> List[str]:
        """
        List available local models
        
        Returns:
            List of model names
        """
        try:
            if self.is_ollama:
                response = self.session.get(
                    f"{self.endpoint}/api/tags",
                    timeout=5
                )
                
                if response.status_code == 200:
                    data = response.json()
                    return [m.get('name', '') for m in data.get('models', [])]
            
            else:
                response = self.session.get(
                    f"{self.endpoint}/v1/models",
                    timeout=5
                )
                
                if response.status_code == 200:
                    data = response.json()
                    return [m.get('id', '') for m in data.get('data', [])]
                    
        except Exception as e:
            print(f"Failed to list models: {str(e)}")
        
        return []
    
    def __repr__(self) -> str:
        return f"LocalModelClient(model={self.model_name}, endpoint={self.endpoint}, ollama={self.is_ollama})"