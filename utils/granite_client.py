"""
Granite API client with retry mechanism and exponential backoff.
Handles transient failures and rate limiting for busy backend services.
"""

import os
import time
import json
import random
import requests
from typing import Dict, Any, Union
from functools import wraps
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class GraniteAPIError(Exception):
    """Custom exception for Granite API errors."""
    pass


class GraniteRateLimitError(GraniteAPIError):
    """Exception for rate limit errors."""
    pass


class GraniteServerError(GraniteAPIError):
    """Exception for server errors (5xx)."""
    pass


def retry_with_exponential_backoff(
    max_retries: int = 5,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    retry_on_status_codes: tuple = (429, 500, 502, 503, 504),
    retry_on_exceptions: tuple = (requests.exceptions.RequestException, GraniteServerError)
):
    """
    Decorator that implements exponential backoff retry logic.
    
    Args:
        max_retries: Maximum number of retry attempts
        base_delay: Initial delay between retries in seconds
        max_delay: Maximum delay between retries in seconds
        exponential_base: Base for exponential backoff calculation
        jitter: Whether to add random jitter to delay
        retry_on_status_codes: HTTP status codes that should trigger retries
        retry_on_exceptions: Exception types that should trigger retries
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    result = func(*args, **kwargs)
                    
                    # If we get here without exception, check if result indicates an error
                    if hasattr(result, 'status_code') and result.status_code in retry_on_status_codes:
                        if result.status_code == 429:
                            raise GraniteRateLimitError(f"Rate limit exceeded: {result.status_code}")
                        elif result.status_code >= 500:
                            raise GraniteServerError(f"Server error: {result.status_code}")
                    
                    return result
                    
                except retry_on_exceptions as e:
                    last_exception = e
                    
                    if attempt == max_retries:
                        print(f"Max retries ({max_retries}) exceeded for {func.__name__}")
                        raise e
                    
                    # Calculate delay with exponential backoff
                    delay = min(base_delay * (exponential_base ** attempt), max_delay)
                    
                    # Add jitter to prevent thundering herd
                    if jitter:
                        delay = delay * (0.5 + random.random() * 0.5)
                    
                    print(f"Attempt {attempt + 1} failed for {func.__name__}: {e}")
                    print(f"Retrying in {delay:.2f} seconds...")
                    time.sleep(delay)
            
            # This shouldn't be reached, but just in case
            if last_exception:
                raise last_exception
                
        return wrapper
    return decorator


class GraniteClient:
    """
    Granite API client with built-in retry logic and error handling.
    """
    
    def __init__(self):
        # Allow both new and legacy environment variable names for compatibility
        self.api_key = (
            os.getenv("GRANITE_INSTRUCT_API_KEY")
            or os.getenv("GRANITE_API_KEY")
        )
        self.api_url = (
            os.getenv("GRANITE_INSTRUCT_URL", "")
            or os.getenv("GRANITE_BASE_URL", "")
        ).rstrip('/')
        self.model_name = (
            os.getenv("GRANITE_INSTRUCT_MODEL_NAME")
            or os.getenv("GRANITE_MODEL")
        )

        # Fallback: detect versioned Granite variables like GRANITE_3_3_8B_INSTRUCT_*
        if not all([self.api_key, self.api_url, self.model_name]):
            # Find any *_INSTRUCT_URL
            url_key = next((k for k in os.environ.keys() if k.endswith("_INSTRUCT_URL") and k.startswith("GRANITE_")), None)
            if url_key:
                prefix = url_key.rsplit("_URL", 1)[0]
                api_key_key = f"{prefix}_API_KEY"
                model_key = f"{prefix}_MODEL_NAME"
                url_val = os.getenv(url_key, "").rstrip('/')
                api_val = os.getenv(api_key_key)
                model_val = os.getenv(model_key)
                # Only apply if all three exist
                if url_val and api_val and model_val:
                    self.api_url = self.api_url or url_val
                    self.api_key = self.api_key or api_val
                    self.model_name = self.model_name or model_val
        
        if not all([self.api_key, self.api_url, self.model_name]):
            raise ValueError("Missing required environment variables for Granite API")
        
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        self.chat_url = f"{self.api_url}/v1/chat/completions"
    
    @retry_with_exponential_backoff(
        max_retries=5,
        base_delay=1.0,
        max_delay=60.0,
        retry_on_status_codes=(429, 500, 502, 503, 504)
    )
    def _make_request(self, payload: Dict[str, Any]) -> requests.Response:
        """
        Make a request to the Granite API with retry logic.
        
        Args:
            payload: The request payload
            
        Returns:
            The response object
            
        Raises:
            GraniteAPIError: For API-specific errors
            GraniteServerError: For server errors (5xx)
            GraniteRateLimitError: For rate limiting (429)
        """
        try:
            response = requests.post(
                self.chat_url, 
                json=payload, 
                headers=self.headers,
                timeout=30  # 30 second timeout
            )
            
            # Check for HTTP errors
            if response.status_code == 429:
                raise GraniteRateLimitError(f"Rate limit exceeded: {response.text}")
            elif response.status_code >= 500:
                raise GraniteServerError(f"Server error {response.status_code}: {response.text}")
            elif response.status_code >= 400:
                raise GraniteAPIError(f"API error {response.status_code}: {response.text}")
            
            return response
            
        except requests.exceptions.Timeout:
            raise GraniteServerError("Request timeout")
        except requests.exceptions.ConnectionError:
            raise GraniteServerError("Connection error")
        except requests.exceptions.RequestException as e:
            raise GraniteAPIError(f"Request failed: {e}")
    
    def call_api_streaming(
        self,
        prompt: str,
        max_tokens: int = 512,
        temperature: float = 0.0,
        stream_callback=None,
        **kwargs
    ):
        """
        Call the Granite API with streaming support.
        
        Args:
            prompt: The input prompt
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature
            stream_callback: Callback function for streaming chunks
            **kwargs: Additional parameters for the API call
            
        Yields:
            Streaming chunks of text
        """
        payload = {
            "model": self.model_name,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": True,  # Enable streaming
            **kwargs
        }
        
        try:
            response = requests.post(
                self.chat_url,
                json=payload,
                headers=self.headers,
                stream=True,
                timeout=30
            )
            
            if response.status_code != 200:
                raise GraniteAPIError(f"API error {response.status_code}: {response.text}")
            
            full_content = ""
            for line in response.iter_lines():
                if line:
                    line = line.decode('utf-8')
                    if line.startswith('data: '):
                        data = line[6:]
                        if data == '[DONE]':
                            break
                        try:
                            chunk = json.loads(data)
                            if 'choices' in chunk and chunk['choices']:
                                delta = chunk['choices'][0].get('delta', {})
                                if 'content' in delta:
                                    content = delta['content']
                                    full_content += content
                                    if stream_callback:
                                        stream_callback(content, chunk)
                                    yield content
                        except json.JSONDecodeError:
                            continue
            
            return full_content
                        
        except requests.exceptions.RequestException as e:
            raise GraniteAPIError(f"Request failed: {e}")
    
    def call_api(
        self, 
        prompt: str, 
        max_tokens: int = 512, 
        temperature: float = 0.0,
        return_metadata: bool = False,
        stream: bool = False,
        stream_callback=None,
        **kwargs
    ) -> Union[str, Dict[str, Any]]:
        """
        Call the Granite API with a prompt and return the response content.
        
        Args:
            prompt: The input prompt
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature
            return_metadata: If True, return dict with content and metadata
            stream: If True, use streaming mode
            stream_callback: Callback for streaming mode
            **kwargs: Additional parameters for the API call
            
        Returns:
            The response content as a string, or dict if return_metadata=True
            
        Raises:
            GraniteAPIError: For API-specific errors
        """
        # Use streaming mode if requested
        if stream:
            content = ""
            for chunk in self.call_api_streaming(prompt, max_tokens, temperature, stream_callback, **kwargs):
                content += chunk
            if return_metadata:
                return {
                    'content': content,
                    'metadata': {
                        'model': self.model_name,
                        'streaming': True
                    }
                }
            return content
        
        # Non-streaming mode (original implementation)
        # Always enable logprobs for confidence scoring
        payload = {
            "model": self.model_name,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": temperature,
            "logprobs": True,  # Always enable logprobs
            **kwargs
        }
        
        try:
            response = self._make_request(payload)
            response_json = response.json()
            
            if 'choices' in response_json and response_json['choices']:
                content = response_json['choices'][0]['message']['content']
                
                if return_metadata:
                    # Extract metadata including logprobs for confidence scoring
                    metadata = {
                        'usage': response_json.get('usage', {}),
                        'model': response_json.get('model', self.model_name),
                        'finish_reason': response_json['choices'][0].get('finish_reason'),
                        'response_time': response.elapsed.total_seconds(),
                        'prompt_tokens': response_json.get('usage', {}).get('prompt_tokens', 0),
                        'completion_tokens': response_json.get('usage', {}).get('completion_tokens', 0),
                        'total_tokens': response_json.get('usage', {}).get('total_tokens', 0),
                        'logprobs': response_json['choices'][0].get('logprobs', {}),  # Include logprobs in metadata
                        'raw_response': response_json  # Include full response for debugging
                    }
                    return {'content': content, 'metadata': metadata}
                else:
                    return content
            else:
                raise GraniteAPIError("No choices found in API response")
                
        except json.JSONDecodeError:
            raise GraniteAPIError(f"Invalid JSON response: {response.text}")
    
    def call_api_with_system_message(
        self,
        system_message: str,
        user_message: str,
        max_tokens: int = 512,
        temperature: float = 0.0,
        return_metadata: bool = False,
        stream: bool = False,
        stream_callback=None,
        **kwargs
    ) -> Union[str, Dict[str, Any]]:
        """
        Call the Granite API with system and user messages.
        
        Args:
            system_message: The system message
            user_message: The user message
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature
            return_metadata: If True, return dict with content and metadata
            stream: If True, use streaming mode
            stream_callback: Callback for streaming mode
            **kwargs: Additional parameters for the API call
            
        Returns:
            The response content as a string, or dict if return_metadata=True
        """
        # Use streaming mode if requested
        if stream:
            content = ""
            payload = {
                "model": self.model_name,
                "messages": [
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": user_message}
                ],
                "max_tokens": max_tokens,
                "temperature": temperature,
                "stream": True,
                **kwargs
            }
            
            try:
                response = requests.post(
                    self.chat_url,
                    json=payload,
                    headers=self.headers,
                    stream=True,
                    timeout=30
                )
                
                if response.status_code != 200:
                    raise GraniteAPIError(f"API error {response.status_code}: {response.text}")
                
                for line in response.iter_lines():
                    if line:
                        line = line.decode('utf-8')
                        if line.startswith('data: '):
                            data = line[6:]
                            if data == '[DONE]':
                                break
                            try:
                                chunk = json.loads(data)
                                if 'choices' in chunk and chunk['choices']:
                                    delta = chunk['choices'][0].get('delta', {})
                                    if 'content' in delta:
                                        chunk_content = delta['content']
                                        content += chunk_content
                                        if stream_callback:
                                            stream_callback(chunk_content, chunk)
                            except json.JSONDecodeError:
                                continue
                
                if return_metadata:
                    return {
                        'content': content,
                        'metadata': {
                            'model': self.model_name,
                            'streaming': True
                        }
                    }
                return content
                
            except requests.exceptions.RequestException as e:
                raise GraniteAPIError(f"Request failed: {e}")
        
        # Non-streaming mode (original implementation)
        # Always enable logprobs for confidence scoring
        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": system_message},
                {"role": "user", "content": user_message}
            ],
            "max_tokens": max_tokens,
            "temperature": temperature,
            "logprobs": True,  # Always enable logprobs
            **kwargs
        }
        
        try:
            response = self._make_request(payload)
            response_json = response.json()
            
            if 'choices' in response_json and response_json['choices']:
                content = response_json['choices'][0]['message']['content']
                
                if return_metadata:
                    # Extract metadata including logprobs for confidence scoring
                    metadata = {
                        'usage': response_json.get('usage', {}),
                        'model': response_json.get('model', self.model_name),
                        'finish_reason': response_json['choices'][0].get('finish_reason'),
                        'response_time': response.elapsed.total_seconds(),
                        'prompt_tokens': response_json.get('usage', {}).get('prompt_tokens', 0),
                        'completion_tokens': response_json.get('usage', {}).get('completion_tokens', 0),
                        'total_tokens': response_json.get('usage', {}).get('total_tokens', 0),
                        'logprobs': response_json['choices'][0].get('logprobs', {}),  # Include logprobs in metadata
                        'raw_response': response_json  # Include full response for debugging
                    }
                    return {'content': content, 'metadata': metadata}
                else:
                    return content
            else:
                raise GraniteAPIError("No choices found in API response")
                
        except json.JSONDecodeError:
            raise GraniteAPIError(f"Invalid JSON response: {response.text}")

    def call_api_with_messages(
        self,
        messages: list,
        max_tokens: int = 512,
        temperature: float = 0.0,
        return_metadata: bool = False,
        **kwargs
    ) -> Union[str, Dict[str, Any]]:
        """
        Call the Granite API with an arbitrary messages array (chat format).
        """
        payload = {
            "model": self.model_name,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "logprobs": True,
            **kwargs
        }
        try:
            response = self._make_request(payload)
            response_json = response.json()
            if 'choices' in response_json and response_json['choices']:
                content = response_json['choices'][0]['message']['content']
                if return_metadata:
                    metadata = {
                        'usage': response_json.get('usage', {}),
                        'model': response_json.get('model', self.model_name),
                        'finish_reason': response_json['choices'][0].get('finish_reason'),
                        'response_time': response.elapsed.total_seconds(),
                        'prompt_tokens': response_json.get('usage', {}).get('prompt_tokens', 0),
                        'completion_tokens': response_json.get('usage', {}).get('completion_tokens', 0),
                        'total_tokens': response_json.get('usage', {}).get('total_tokens', 0),
                        'logprobs': response_json['choices'][0].get('logprobs', {}),
                        'raw_response': response_json
                    }
                    return {'content': content, 'metadata': metadata}
                else:
                    return content
            else:
                raise GraniteAPIError("No choices found in API response")
        except json.JSONDecodeError:
            raise GraniteAPIError(f"Invalid JSON response: {response.text}")


# Create a global instance for convenience
granite_client = GraniteClient()


# Backward compatibility function
@retry_with_exponential_backoff(max_retries=3)
def call_granite_api(prompt: str, **kwargs) -> str:
    """
    Backward compatibility function for calling Granite API.
    
    Args:
        prompt: The prompt to send to the model
        **kwargs: Additional parameters for the API call
        
    Returns:
        Generated text
    """
    # Force return_metadata to False to ensure string return type
    kwargs['return_metadata'] = False
    result = granite_client.call_api(prompt, **kwargs)
    assert isinstance(result, str), "Expected string result"
    return result