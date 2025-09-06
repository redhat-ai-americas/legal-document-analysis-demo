"""
Mixtral API client for validation tasks.

This module provides a client for interacting with the Mixtral API,
primarily used for validation of classification results.
"""

import os
import time
import json
import logging
from typing import Dict, Any, Union
import requests
from functools import wraps
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logger = logging.getLogger(__name__)


class MixtralAPIError(Exception):
    """Custom exception for Mixtral API errors."""
    pass


class MixtralRateLimitError(MixtralAPIError):
    """Exception for rate limit errors."""
    pass


class MixtralServerError(MixtralAPIError):
    """Exception for server errors (5xx)."""
    pass


def retry_with_exponential_backoff(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    retry_on_status_codes: tuple = (429, 500, 502, 503, 504)
):
    """
    Decorator for retrying functions with exponential backoff.
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            delay = base_delay
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except requests.exceptions.HTTPError as e:
                    last_exception = e
                    status_code = e.response.status_code if e.response else None
                    
                    if status_code not in retry_on_status_codes or attempt == max_retries:
                        raise
                    
                    logger.warning(
                        f"Mixtral request failed with status {status_code}. "
                        f"Attempt {attempt + 1}/{max_retries + 1}. "
                        f"Retrying in {delay:.1f} seconds..."
                    )
                    
                except (requests.exceptions.ConnectionError, 
                       requests.exceptions.Timeout,
                       requests.exceptions.RequestException) as e:
                    last_exception = e
                    if attempt == max_retries:
                        raise
                    
                    logger.warning(
                        f"Mixtral request failed with {type(e).__name__}. "
                        f"Attempt {attempt + 1}/{max_retries + 1}. "
                        f"Retrying in {delay:.1f} seconds..."
                    )
                
                # Apply backoff
                time.sleep(delay)
                
                # Calculate next delay with exponential backoff
                delay = min(delay * exponential_base, max_delay)
                
                # Add jitter if enabled
                if jitter:
                    import random
                    delay *= (0.5 + random.random())
            
            # If we get here, all retries failed
            raise last_exception
        
        return wrapper
    return decorator


class MixtralClient:
    """Client for interacting with the Mixtral API."""
    
    def __init__(self):
        """Initialize the Mixtral client with configuration from environment variables."""
        self.api_key = os.getenv('MIXTRAL_API_KEY')
        self.api_url = os.getenv('MIXTRAL_URL')
        self.model_name = os.getenv('MIXTRAL_MODEL_NAME', 'mistralai/Mixtral-8x7B-Instruct-v0.1')
        
        if not self.api_key:
            raise ValueError("MIXTRAL_API_KEY environment variable is required")
        if not self.api_url:
            raise ValueError("MIXTRAL_URL environment variable is required")
        
        # Build endpoint URL
        self.endpoint = f"{self.api_url}/v1/chat/completions"
        
        # Set up headers
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        logger.info(f"Mixtral client initialized with model: {self.model_name}")
    
    @retry_with_exponential_backoff()
    def _make_request(self, payload: Dict[str, Any]) -> requests.Response:
        """
        Make a request to the Mixtral API with retry logic.
        
        Args:
            payload: Request payload
            
        Returns:
            Response object
            
        Raises:
            MixtralAPIError: For API-specific errors
        """
        try:
            response = requests.post(
                self.endpoint,
                json=payload,
                headers=self.headers,
                timeout=60
            )
            
            # Check for HTTP errors
            if response.status_code == 429:
                raise MixtralRateLimitError(f"Rate limit exceeded: {response.text}")
            elif response.status_code >= 500:
                raise MixtralServerError(f"Server error {response.status_code}: {response.text}")
            elif response.status_code >= 400:
                raise MixtralAPIError(f"Client error {response.status_code}: {response.text}")
            
            response.raise_for_status()
            return response
            
        except requests.exceptions.ConnectionError as e:
            raise MixtralAPIError(f"Failed to connect to Mixtral server: {e}")
        except requests.exceptions.Timeout as e:
            raise MixtralAPIError(f"Request timed out: {e}")
        except requests.exceptions.RequestException as e:
            raise MixtralAPIError(f"Request failed: {e}")
    
    def call_api(
        self,
        prompt: str,
        max_tokens: int = 256,
        temperature: float = 0.0,
        return_metadata: bool = False,
        **kwargs
    ) -> Union[str, Dict[str, Any]]:
        """
        Call the Mixtral API with the given prompt.
        
        Args:
            prompt: The prompt to send to the model
            max_tokens: Maximum number of tokens to generate
            temperature: Sampling temperature (0.0 = deterministic)
            return_metadata: Whether to return full response with metadata
            **kwargs: Additional parameters to pass to the API
            
        Returns:
            Generated text or full response dict if return_metadata=True
            
        Raises:
            MixtralAPIError: If the API request fails
        """
        payload = {
            "model": self.model_name,
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
            **kwargs
        }
        
        response = self._make_request(payload)
        
        try:
            response_json = response.json()
        except json.JSONDecodeError as e:
            raise MixtralAPIError(f"Failed to parse response JSON: {e}")
        
        # Extract the response content
        choices = response_json.get("choices", [])
        if not choices:
            raise MixtralAPIError("No choices in API response")
        
        content = choices[0].get("message", {}).get("content", "")
        
        if return_metadata:
            return {
                "content": content,
                "metadata": {
                    "model": response_json.get("model", self.model_name),
                    "usage": response_json.get("usage", {}),
                    "finish_reason": choices[0].get("finish_reason"),
                    "created": response_json.get("created")
                }
            }
        
        return content
    
    def call_api_with_system_message(
        self,
        system_message: str,
        user_message: str,
        max_tokens: int = 256,
        temperature: float = 0.0,
        return_metadata: bool = False,
        **kwargs
    ) -> Union[str, Dict[str, Any]]:
        """
        Call the Mixtral API with system and user messages.
        
        Args:
            system_message: System prompt to set context
            user_message: User message/prompt
            max_tokens: Maximum number of tokens to generate
            temperature: Sampling temperature
            return_metadata: Whether to return full response with metadata
            **kwargs: Additional parameters
            
        Returns:
            Generated text or full response dict if return_metadata=True
        """
        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": system_message},
                {"role": "user", "content": user_message}
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
            **kwargs
        }
        
        response = self._make_request(payload)
        
        try:
            response_json = response.json()
        except json.JSONDecodeError as e:
            raise MixtralAPIError(f"Failed to parse response JSON: {e}")
        
        # Extract the response content
        choices = response_json.get("choices", [])
        if not choices:
            raise MixtralAPIError("No choices in API response")
        
        content = choices[0].get("message", {}).get("content", "")
        
        if return_metadata:
            return {
                "content": content,
                "metadata": {
                    "model": response_json.get("model", self.model_name),
                    "usage": response_json.get("usage", {}),
                    "finish_reason": choices[0].get("finish_reason"),
                    "created": response_json.get("created")
                }
            }
        
        return content


# Create a global instance for convenience
mixtral_client = MixtralClient()


# Backward compatibility function
def call_mixtral_api(prompt: str, max_tokens: int = 256, temperature: float = 0.0, **kwargs) -> str:
    """
    Backward compatibility function for calling Mixtral API.
    
    Args:
        prompt: The prompt to send to the model
        max_tokens: Maximum number of tokens to generate
        temperature: Sampling temperature
        **kwargs: Additional parameters
        
    Returns:
        Generated text
    """
    return mixtral_client.call_api(prompt, max_tokens, temperature, **kwargs)