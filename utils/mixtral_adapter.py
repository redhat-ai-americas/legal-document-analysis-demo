"""
Mixtral support removed. This module is kept as a stub to prevent accidental use.
"""

from typing import Dict, Any, Union, cast  # noqa: F401

class MixtralAdapter:
    """Stub adapter that raises to indicate Mixtral is no longer supported."""
    def call_api(self, *args, **kwargs) -> str:
        raise RuntimeError("Mixtral support removed: Granite-only configuration")
    def call_api_with_system_message(self, *args, **kwargs) -> str:
        raise RuntimeError("Mixtral support removed: Granite-only configuration")


# Create a global instance for convenience
mixtral_client = MixtralAdapter()


# Backward compatibility function
def call_mixtral_api(*args, **kwargs) -> str:
    raise RuntimeError("Mixtral support removed: Granite-only configuration")