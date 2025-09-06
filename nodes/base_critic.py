"""
Base Critic Class for All Critic Agents

This module provides the base class and common functionality for all critic agents
in the contract analysis workflow.
"""

from typing import Dict, Any, List
from dataclasses import dataclass, field
from enum import Enum
import os
from dotenv import load_dotenv

load_dotenv()

class CriticSeverity(Enum):
    """Severity levels for critic findings"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

@dataclass
class ValidationResult:
    """Result of a critic's validation"""
    is_valid: bool
    severity: CriticSeverity
    issues: List[str]
    recommendations: List[str]
    metrics: Dict[str, Any]
    should_retry: bool = False
    retry_params: Dict[str, Any] = field(default_factory=dict)

class BaseCritic:
    """Base class for all critic agents"""
    
    def __init__(self, name: str, max_retries: int = None):
        """
        Initialize the base critic.
        
        Args:
            name: Name of the critic (e.g., "entity_extraction")
            max_retries: Maximum number of retries allowed
        """
        self.name = name
        self.max_retries = max_retries or self._get_env_max_retries()
        self.enabled = self._get_env_enabled()
        
    def _get_env_max_retries(self) -> int:
        """Get max retries from environment variable"""
        env_var = f"{self.name.upper()}_CRITIC_MAX_RETRIES"
        return int(os.getenv(env_var, "2"))
    
    def _get_env_enabled(self) -> bool:
        """Check if critic is enabled via environment variable"""
        env_var = f"{self.name.upper()}_CRITIC_ENABLED"
        return os.getenv(env_var, "true").lower() == "true"
    
    def validate(self, state: Dict[str, Any]) -> ValidationResult:
        """
        Perform validation checks on the state.
        Must be implemented by subclasses.
        
        Args:
            state: Current workflow state
            
        Returns:
            ValidationResult with findings and recommendations
        """
        raise NotImplementedError("Subclasses must implement validate()")
    
    def should_retry(self, validation_result: ValidationResult, attempts: int) -> bool:
        """
        Determine if retry is warranted based on validation results.
        
        Args:
            validation_result: Result from validation
            attempts: Number of attempts already made
            
        Returns:
            True if should retry, False otherwise
        """
        if not self.enabled:
            return False
            
        if attempts >= self.max_retries:
            return False
            
        return validation_result.should_retry
    
    def prepare_retry_state(self, state: Dict[str, Any], validation_result: ValidationResult) -> Dict[str, Any]:
        """
        Modify state for retry with improvements.
        Can be overridden by subclasses for specific retry strategies.
        
        Args:
            state: Current workflow state
            validation_result: Result from validation
            
        Returns:
            Modified state for retry
        """
        # Update attempt counter
        attempts_key = f"{self.name}_critic_attempts"
        state[attempts_key] = state.get(attempts_key, 0) + 1
        
        # Store recommendations for audit trail
        recommendations_key = f"{self.name}_critic_recommendations"
        if recommendations_key not in state:
            state[recommendations_key] = []
        state[recommendations_key].extend(validation_result.recommendations)
        
        # Apply retry parameters if provided
        if validation_result.retry_params:
            for key, value in validation_result.retry_params.items():
                state[key] = value
        
        return state
    
    def format_issues_message(self, issues: List[str]) -> str:
        """Format issues list into a readable message"""
        if not issues:
            return "No issues found"
        return "\n".join(f"• {issue}" for issue in issues)
    
    def format_recommendations_message(self, recommendations: List[str]) -> str:
        """Format recommendations list into a readable message"""
        if not recommendations:
            return "No recommendations"
        return "\n".join(f"• {rec}" for rec in recommendations)
    
    def log_validation_result(self, result: ValidationResult) -> None:
        """Log validation results for debugging"""
        print(f"\n{'='*60}")
        print(f"{self.name.upper()} CRITIC VALIDATION RESULT")
        print(f"{'='*60}")
        print(f"Valid: {result.is_valid}")
        print(f"Severity: {result.severity.value}")
        
        if result.issues:
            print("\nIssues Found:")
            print(self.format_issues_message(result.issues))
        
        if result.recommendations:
            print("\nRecommendations:")
            print(self.format_recommendations_message(result.recommendations))
        
        if result.metrics:
            print("\nMetrics:")
            for key, value in result.metrics.items():
                print(f"  {key}: {value}")
        
        print(f"{'='*60}\n")

def create_critic_node(critic_class):
    """
    Factory function to create a LangGraph node from a critic class.
    
    Args:
        critic_class: A subclass of BaseCritic
        
    Returns:
        A node function that can be used in LangGraph
    """
    def critic_node(state: Dict[str, Any]) -> Dict[str, Any]:
        """Node function for the critic"""
        critic = critic_class()
        
        if not critic.enabled:
            print(f"{critic.name} critic is disabled, skipping...")
            return state
        
        # Perform validation
        result = critic.validate(state)
        
        # Log results
        critic.log_validation_result(result)
        
        # Store validation result in state
        state[f"{critic.name}_validation_result"] = {
            "is_valid": result.is_valid,
            "severity": result.severity.value,
            "issues": result.issues,
            "recommendations": result.recommendations,
            "metrics": result.metrics
        }
        
        return state
    
    return critic_node

def create_retry_condition(critic_class):
    """
    Factory function to create a retry condition function for a critic.
    
    Args:
        critic_class: A subclass of BaseCritic
        
    Returns:
        A condition function that determines if retry is needed
    """
    def should_retry(state: Dict[str, Any]) -> str:
        """Condition function to determine if retry is needed"""
        critic = critic_class()
        
        if not critic.enabled:
            return "continue"
        
        # Get validation result from state
        validation_key = f"{critic.name}_validation_result"
        if validation_key not in state:
            return "continue"
        
        validation_data = state[validation_key]
        result = ValidationResult(
            is_valid=validation_data["is_valid"],
            severity=CriticSeverity(validation_data["severity"]),
            issues=validation_data["issues"],
            recommendations=validation_data["recommendations"],
            metrics=validation_data["metrics"],
            should_retry=not validation_data["is_valid"] and 
                       validation_data["severity"] in ["error", "critical"]
        )
        
        # Check attempts
        attempts_key = f"{critic.name}_critic_attempts"
        attempts = state.get(attempts_key, 0)
        
        if critic.should_retry(result, attempts):
            # Prepare state for retry
            state = critic.prepare_retry_state(state, result)
            return "retry"
        
        return "continue"
    
    return should_retry