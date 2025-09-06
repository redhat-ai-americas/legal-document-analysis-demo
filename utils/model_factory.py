"""
Model Factory for creating appropriate model clients
Supports dynamic model selection based on configuration
"""

import os
from typing import Optional, Dict
from enum import Enum

from utils.model_client import ModelClient, ModelConfig
from utils.granite_model_client import GraniteModelClient
from utils.local_model_client import LocalModelClient
from utils.mixtral_client import MixtralClient


class ModelType(Enum):
    """Supported model types"""
    GRANITE = "granite"
    LOCAL = "local"
    OLLAMA = "ollama"
    MIXTRAL = "mixtral"
    AUTO = "auto"


class ModelFactory:
    """Factory for creating model clients based on configuration"""
    
    # Model type mappings
    MODEL_PATTERNS = {
        ModelType.GRANITE: ["granite", "ibm"],
        ModelType.MIXTRAL: ["mixtral", "mistral"],
        ModelType.OLLAMA: ["llama", "ollama", "phi", "gemma", "codellama"],
        ModelType.LOCAL: ["local", "custom"]
    }
    
    @classmethod
    def create_client(
        cls,
        model_name: Optional[str] = None,
        model_type: Optional[ModelType] = None,
        **config_kwargs
    ) -> ModelClient:
        """
        Create a model client based on configuration
        
        Args:
            model_name: Name of the model to use
            model_type: Type of model (granite, local, etc.)
            **config_kwargs: Additional configuration parameters
            
        Returns:
            Appropriate ModelClient instance
        """
        # Get model name from env if not provided
        if not model_name:
            model_name = os.getenv('DEFAULT_MODEL', 'granite-3.3')
        
        # Auto-detect model type if not specified
        if not model_type or model_type == ModelType.AUTO:
            model_type = cls._detect_model_type(model_name)
        
        # Create configuration
        config = ModelConfig(
            model_name=model_name,
            **config_kwargs
        )
        
        # Create appropriate client
        if model_type == ModelType.GRANITE:
            return GraniteModelClient(config)
        elif model_type == ModelType.MIXTRAL:
            # Use existing MixtralClient if available
            try:
                return MixtralClient(config)
            except:
                # Fallback to Granite if Mixtral not available
                print("Mixtral client not available, using Granite")
                return GraniteModelClient(config)
        elif model_type in (ModelType.LOCAL, ModelType.OLLAMA):
            return LocalModelClient(config)
        else:
            # Default to Granite
            return GraniteModelClient(config)
    
    @classmethod
    def _detect_model_type(cls, model_name: str) -> ModelType:
        """
        Auto-detect model type from model name
        
        Args:
            model_name: Name of the model
            
        Returns:
            Detected ModelType
        """
        model_lower = model_name.lower()
        
        # Check patterns
        for model_type, patterns in cls.MODEL_PATTERNS.items():
            if any(pattern in model_lower for pattern in patterns):
                return model_type
        
        # Check environment hints
        if os.getenv('USE_LOCAL_MODELS', '').lower() in ('true', '1', 'yes'):
            return ModelType.LOCAL
        
        # Default to Granite
        return ModelType.GRANITE
    
    @classmethod
    def create_multi_model_client(
        cls,
        primary_model: str,
        secondary_model: Optional[str] = None,
        **config_kwargs
    ) -> Dict[str, ModelClient]:
        """
        Create multiple model clients for validation/comparison
        
        Args:
            primary_model: Primary model name
            secondary_model: Optional secondary model for validation
            **config_kwargs: Additional configuration
            
        Returns:
            Dictionary of model clients
        """
        clients = {}
        
        # Create primary client
        clients['primary'] = cls.create_client(
            model_name=primary_model,
            **config_kwargs
        )
        
        # Create secondary if specified
        if secondary_model:
            clients['secondary'] = cls.create_client(
                model_name=secondary_model,
                **config_kwargs
            )
        
        # Add validator model if configured
        validator_model = os.getenv('VALIDATOR_MODEL')
        if validator_model and validator_model != primary_model:
            clients['validator'] = cls.create_client(
                model_name=validator_model,
                **config_kwargs
            )
        
        return clients
    
    @classmethod
    def get_available_models(cls) -> Dict[str, bool]:
        """
        Check availability of different model types
        
        Returns:
            Dictionary of model types and their availability
        """
        availability = {}
        
        # Check Granite
        try:
            granite = cls.create_client(
                model_name="granite-3.3",
                model_type=ModelType.GRANITE
            )
            availability['granite'] = granite.is_available()
        except:
            availability['granite'] = False
        
        # Check local/Ollama
        try:
            local = cls.create_client(
                model_name="llama3",
                model_type=ModelType.LOCAL
            )
            availability['local'] = local.is_available()
        except:
            availability['local'] = False
        
        # Check Mixtral
        try:
            mixtral = cls.create_client(
                model_name="mixtral-8x7b",
                model_type=ModelType.MIXTRAL
            )
            availability['mixtral'] = mixtral.is_available()
        except:
            availability['mixtral'] = False
        
        return availability
    
    @classmethod
    def get_recommended_model(cls) -> str:
        """
        Get recommended model based on availability and configuration
        
        Returns:
            Recommended model name
        """
        # Check feature flags
        use_v2_models = os.getenv('USE_V2_MODELS', 'false').lower() in ('true', '1', 'yes')
        
        if use_v2_models:
            # V2 architecture preferences
            availability = cls.get_available_models()
            
            # Prefer Granite 3.3 for v2
            if availability.get('granite'):
                return 'granite-3.3'
            
            # Fallback to local if available
            if availability.get('local'):
                return 'llama3:8b'
            
            # Last resort
            return 'granite-3.3'
        
        else:
            # Legacy configuration
            return os.getenv('DEFAULT_MODEL', 'granite-3.3')
    
    @classmethod
    def create_from_env(cls) -> ModelClient:
        """
        Create a model client from environment configuration
        
        Returns:
            Configured ModelClient
        """
        model_name = os.getenv('MODEL_NAME') or cls.get_recommended_model()
        
        # Get configuration from env
        config_kwargs = {
            'temperature': float(os.getenv('MODEL_TEMPERATURE', '0.1')),
            'max_tokens': int(os.getenv('MODEL_MAX_TOKENS', '2000')),
            'top_p': float(os.getenv('MODEL_TOP_P', '0.95')),
            'timeout': int(os.getenv('MODEL_TIMEOUT', '30')),
        }
        
        return cls.create_client(
            model_name=model_name,
            **config_kwargs
        )


# Convenience function for backward compatibility
def get_model_client(model_name: str = None, **kwargs):
    """
    Get a model client (backward compatibility)
    
    Args:
        model_name: Model name or None for auto-selection
        **kwargs: Additional configuration
        
    Returns:
        ModelClient instance
    """
    if model_name is None:
        model_name = ModelFactory.get_recommended_model()
    
    return ModelFactory.create_client(model_name, **kwargs)