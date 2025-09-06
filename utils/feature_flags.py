"""
Feature Flag System for gradual v2 architecture rollout
Supports percentage-based rollouts and explicit overrides
"""

import os
import yaml
import hashlib
import random
from typing import Dict, Any, Optional
from pathlib import Path
from dataclasses import dataclass


@dataclass
class Feature:
    """Represents a single feature flag"""
    name: str
    enabled: bool
    description: str
    rollout_percentage: int
    config: Dict[str, Any]
    
    def is_enabled_for(self, identifier: Optional[str] = None) -> bool:
        """
        Check if feature is enabled for a specific identifier
        
        Args:
            identifier: User/document identifier for consistent rollout
            
        Returns:
            True if feature is enabled
        """
        if not self.enabled:
            return False
        
        if self.rollout_percentage >= 100:
            return True
        
        if self.rollout_percentage <= 0:
            return False
        
        # Use identifier for consistent rollout
        if identifier:
            hash_val = int(hashlib.md5(f"{self.name}:{identifier}".encode()).hexdigest(), 16)
            return (hash_val % 100) < self.rollout_percentage
        
        # Random rollout if no identifier
        return random.random() * 100 < self.rollout_percentage


class FeatureFlags:
    """Manages feature flags for the application"""
    
    _instance = None
    _features: Dict[str, Feature] = {}
    _config: Dict[str, Any] = {}
    
    def __new__(cls):
        """Singleton pattern for feature flags"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """Initialize feature flags from configuration"""
        if not self._initialized:
            self.load_config()
            self._initialized = True
    
    def load_config(self, config_path: Optional[str] = None):
        """
        Load feature flags configuration from YAML file
        
        Args:
            config_path: Path to configuration file
        """
        if not config_path:
            # Default config paths
            possible_paths = [
                Path(__file__).parent.parent / "config" / "feature_flags.yaml",
                Path.cwd() / "config" / "feature_flags.yaml",
                Path.home() / "." / "feature_flags.yaml"
            ]
            
            for path in possible_paths:
                if path.exists():
                    config_path = str(path)
                    break
        
        if config_path and Path(config_path).exists():
            with open(config_path, 'r') as f:
                self._config = yaml.safe_load(f)
                self._parse_features()
        else:
            # Default configuration if no file found
            self._config = {
                'features': {},
                'rollout': {'method': 'percentage'}
            }
    
    def _parse_features(self):
        """Parse features from configuration"""
        features_config = self._config.get('features', {})
        
        for name, config in features_config.items():
            # Check for environment override
            env_key = f"FEATURE_{name.upper()}"
            env_enabled = os.getenv(env_key)
            
            if env_enabled is not None:
                enabled = env_enabled.lower() in ('true', '1', 'yes', 'on')
            else:
                enabled = config.get('enabled', False)
            
            self._features[name] = Feature(
                name=name,
                enabled=enabled,
                description=config.get('description', ''),
                rollout_percentage=config.get('rollout_percentage', 0),
                config=config
            )
    
    def is_enabled(
        self,
        feature_name: str,
        identifier: Optional[str] = None
    ) -> bool:
        """
        Check if a feature is enabled
        
        Args:
            feature_name: Name of the feature
            identifier: Optional identifier for consistent rollout
            
        Returns:
            True if feature is enabled
        """
        # Check environment override first
        env_key = f"FEATURE_{feature_name.upper()}"
        env_value = os.getenv(env_key)
        if env_value is not None:
            return env_value.lower() in ('true', '1', 'yes', 'on')
        
        # Check always enabled/disabled lists
        if identifier:
            always_enabled = self._config.get('rollout', {}).get('always_enabled_for', [])
            if identifier in always_enabled:
                return True
            
            always_disabled = self._config.get('rollout', {}).get('always_disabled_for', [])
            if identifier in always_disabled:
                return False
        
        # Check feature configuration
        feature = self._features.get(feature_name)
        if feature:
            return feature.is_enabled_for(identifier)
        
        # Default to disabled for unknown features
        return False
    
    def get_config(self, feature_name: str) -> Dict[str, Any]:
        """
        Get configuration for a feature
        
        Args:
            feature_name: Name of the feature
            
        Returns:
            Feature configuration dictionary
        """
        feature = self._features.get(feature_name)
        return feature.config if feature else {}
    
    def get_all_features(self) -> Dict[str, bool]:
        """
        Get status of all features
        
        Returns:
            Dictionary of feature names to enabled status
        """
        return {
            name: feature.enabled
            for name, feature in self._features.items()
        }
    
    def enable_feature(self, feature_name: str, rollout_percentage: int = 100):
        """
        Enable a feature programmatically
        
        Args:
            feature_name: Name of the feature
            rollout_percentage: Rollout percentage (0-100)
        """
        if feature_name in self._features:
            self._features[feature_name].enabled = True
            self._features[feature_name].rollout_percentage = rollout_percentage
        else:
            # Create new feature
            self._features[feature_name] = Feature(
                name=feature_name,
                enabled=True,
                description=f"Dynamically enabled feature: {feature_name}",
                rollout_percentage=rollout_percentage,
                config={}
            )
    
    def disable_feature(self, feature_name: str):
        """
        Disable a feature programmatically
        
        Args:
            feature_name: Name of the feature
        """
        if feature_name in self._features:
            self._features[feature_name].enabled = False
            self._features[feature_name].rollout_percentage = 0
    
    def with_feature(self, feature_name: str):
        """
        Decorator for feature-flagged functions
        
        Args:
            feature_name: Name of the feature
            
        Returns:
            Decorator function
        """
        def decorator(func):
            def wrapper(*args, **kwargs):
                # Try to extract identifier from kwargs or args
                identifier = kwargs.get('identifier') or kwargs.get('document_path')
                
                if self.is_enabled(feature_name, identifier):
                    return func(*args, **kwargs)
                else:
                    # Return None or raise based on function
                    return None
            
            return wrapper
        return decorator
    
    def log_feature_usage(self, feature_name: str, identifier: Optional[str] = None):
        """
        Log feature usage for monitoring
        
        Args:
            feature_name: Name of the feature
            identifier: Optional identifier
        """
        enabled = self.is_enabled(feature_name, identifier)
        print(f"Feature '{feature_name}' checked: {'ENABLED' if enabled else 'DISABLED'}")
    
    def __repr__(self) -> str:
        enabled_count = sum(1 for f in self._features.values() if f.enabled)
        return f"FeatureFlags({enabled_count}/{len(self._features)} features enabled)"


# Global instance
feature_flags = FeatureFlags()


# Convenience functions
def is_feature_enabled(feature_name: str, identifier: Optional[str] = None) -> bool:
    """
    Check if a feature is enabled
    
    Args:
        feature_name: Name of the feature
        identifier: Optional identifier for consistent rollout
        
    Returns:
        True if feature is enabled
    """
    return feature_flags.is_enabled(feature_name, identifier)


def get_feature_config(feature_name: str) -> Dict[str, Any]:
    """
    Get configuration for a feature
    
    Args:
        feature_name: Name of the feature
        
    Returns:
        Feature configuration dictionary
    """
    return feature_flags.get_config(feature_name)


def with_feature(feature_name: str):
    """
    Decorator for feature-flagged functions
    
    Args:
        feature_name: Name of the feature
        
    Returns:
        Decorator function
    """
    return feature_flags.with_feature(feature_name)