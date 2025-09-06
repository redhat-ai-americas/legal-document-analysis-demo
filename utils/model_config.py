"""
Model configuration management for the workflow.

This module provides configuration management for controlling which models
are used and how they are configured. Designed to support multiple models
per node in the future.
"""

import os
from typing import Dict, Any
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class ModelConfig:
    """Configuration manager for model selection and settings."""
    
    def __init__(self):
        """Initialize model configuration from environment variables."""
        # Primary model selection
        self.primary_model = os.getenv('PRIMARY_MODEL', 'granite')
        
        # Granite model configuration
        self.granite_config = {
            'temperature': float(os.getenv('GRANITE_TEMPERATURE', '0.1')),
            'max_tokens': int(os.getenv('GRANITE_MAX_TOKENS', '256')),
            'retry_attempts': int(os.getenv('GRANITE_RETRY_ATTEMPTS', '5'))
        }
        
        # Performance settings
        self.parallel_processing = self._get_bool_env('PARALLEL_PROCESSING', True)
        self.max_workers = int(os.getenv('MAX_WORKERS', '2'))
        self.timeout_seconds = int(os.getenv('MODEL_TIMEOUT_SECONDS', '120'))
        
        # Fallback settings
        self.fallback_enabled = self._get_bool_env('FALLBACK_ENABLED', True)
        self.fallback_model = os.getenv('FALLBACK_MODEL', 'granite')
    
    def _get_bool_env(self, key: str, default: bool) -> bool:
        """Get boolean environment variable with default."""
        value = os.getenv(key, str(default)).lower()
        return value in ('true', '1', 'yes', 'on')
    
    def get_active_models(self) -> list:
        """Get list of active models based on configuration."""
        return [self.primary_model]
    
    def get_model_config(self, model_name: str = None) -> Dict[str, Any]:
        """
        Get configuration for a specific model.
        
        Args:
            model_name: Name of the model. If None, uses primary model.
            
        Returns:
            Model configuration dictionary
        """
        if model_name is None or model_name == 'granite':
            return self.granite_config.copy()
        else:
            # Future: Add support for other models here
            raise ValueError(f"Unknown model: {model_name}")
    
    def get_processing_config(self) -> Dict[str, Any]:
        """Get processing configuration."""
        return {
            'parallel_processing': self.parallel_processing,
            'max_workers': self.max_workers,
            'timeout_seconds': self.timeout_seconds
        }
    
    def get_fallback_config(self) -> Dict[str, Any]:
        """Get fallback configuration."""
        return {
            'enabled': self.fallback_enabled,
            'fallback_model': self.fallback_model
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """Export configuration as dictionary."""
        return {
            'primary_model': self.primary_model,
            'granite_config': self.granite_config,
            'processing': self.get_processing_config(),
            'fallback': self.get_fallback_config()
        }


# Global configuration instance
model_config = ModelConfig()


def get_questionnaire_processor():
    """
    Get the appropriate questionnaire processor based on configuration.
    
    Returns:
        The processor function to use
    """
    # Check if enhanced attribution tracking is enabled
    if os.getenv('USE_ENHANCED_ATTRIBUTION', '').lower() in ('1', 'true', 'yes', 'on'):
        from nodes.questionnaire_processor_enhanced import process_questionnaire_enhanced
        return process_questionnaire_enhanced
    else:
        # Use standard Granite processor
        from nodes.questionnaire_processor import process_questionnaire
        return process_questionnaire


def get_model_configs() -> Dict[str, Dict[str, Any]]:
    """Get all model configurations."""
    return {
        'granite': model_config.get_model_config('granite')
    }


# Backward compatibility functions (will be deprecated)
def is_dual_model_enabled() -> bool:
    """Check if dual-model processing is enabled. Kept for backward compatibility."""
    return False