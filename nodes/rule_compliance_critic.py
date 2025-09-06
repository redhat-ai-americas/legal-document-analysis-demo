"""
Rule Compliance Logic Critic

This critic validates the quality of rule compliance evaluation.
It checks for not_evaluated rules, empty evidence, conflicting determinations,
and ensures critical rules have been properly assessed.
"""

from typing import Dict, Any, List
from nodes.base_critic import BaseCritic, ValidationResult, CriticSeverity, create_critic_node

class RuleComplianceCritic(BaseCritic):
    """Critic to validate rule compliance evaluation quality"""
    
    def __init__(self):
        super().__init__("rule_compliance")
        # Rules that should always have matches in typical contracts
        self.critical_rules = {
            "governing_law",
            "dispute_resolution",
            "termination",
            "confidentiality",
            "liability",
            "indemnification"
        }
    
    def validate(self, state: Dict[str, Any]) -> ValidationResult:
        """
        Validate rule compliance evaluation quality.
        
        Args:
            state: Current workflow state
            
        Returns:
            ValidationResult with findings
        """
        issues = []
        recommendations = []
        metrics = {}
        severity = CriticSeverity.INFO
        
        # Get rule compliance results from state
        rule_results = state.get("rule_compliance_results", {})
        
        # If no rules were evaluated (might be intentional)
        if not rule_results:
            if state.get("rules_file"):
                issues.append("Rules file provided but no rules were evaluated")
                severity = CriticSeverity.ERROR
                recommendations.append("Check rules loader and compliance checker")
            # No rules file, so no compliance checking is expected
            return ValidationResult(
                is_valid=True,
                severity=CriticSeverity.INFO,
                issues=[],
                recommendations=[],
                metrics={"rules_evaluated": 0},
                should_retry=False
            )
        
        # Analyze rule evaluation results
        total_rules = len(rule_results)
        not_evaluated = []
        no_evidence = []
        conflicting = []
        critical_missing = []
        
        for rule_id, result in rule_results.items():
            status = result.get("status", "not_evaluated")
            evidence = result.get("evidence", [])
            
            # Check for not evaluated rules
            if status == "not_evaluated":
                not_evaluated.append(rule_id)
            
            # Check for rules with no evidence
            elif status in ["compliant", "non_compliant"] and not evidence:
                no_evidence.append(rule_id)
            
            # Check for conflicting evidence (both compliant and non-compliant indicators)
            if self._has_conflicting_evidence(result):
                conflicting.append(rule_id)
            
            # Check if critical rules are missing
            if any(critical in rule_id.lower() for critical in self.critical_rules):
                if status == "not_evaluated" or not evidence:
                    critical_missing.append(rule_id)
        
        # Calculate metrics
        metrics["total_rules"] = total_rules
        metrics["evaluated_rules"] = total_rules - len(not_evaluated)
        metrics["not_evaluated_ratio"] = len(not_evaluated) / total_rules if total_rules > 0 else 0
        metrics["no_evidence_count"] = len(no_evidence)
        metrics["conflicting_count"] = len(conflicting)
        metrics["critical_missing"] = len(critical_missing)
        
        # Identify issues
        if metrics["not_evaluated_ratio"] > 0.5:
            issues.append(f"{len(not_evaluated)}/{total_rules} rules were not evaluated")
            severity = CriticSeverity.ERROR
            recommendations.append("Retry with retrieval fallback for unevaluated rules")
        elif metrics["not_evaluated_ratio"] > 0.3:
            issues.append(f"{len(not_evaluated)} rules not evaluated")
            severity = max(severity, CriticSeverity.WARNING)
        
        if no_evidence:
            issues.append(f"{len(no_evidence)} rules have determinations without evidence")
            recommendations.append("Retry with expanded evidence search")
            severity = max(severity, CriticSeverity.WARNING)
        
        if conflicting:
            issues.append(f"{len(conflicting)} rules have conflicting evidence")
            recommendations.append("Apply enhanced reasoning to resolve conflicts")
            severity = max(severity, CriticSeverity.ERROR)
        
        if critical_missing:
            issues.append(f"Critical rules not properly evaluated: {', '.join(critical_missing[:3])}")
            recommendations.append("Focus retrieval on critical compliance areas")
            severity = CriticSeverity.ERROR
        
        # Check for suspicious patterns
        all_compliant = all(
            r.get("status") == "compliant" 
            for r in rule_results.values() 
            if r.get("status") != "not_evaluated"
        )
        all_non_compliant = all(
            r.get("status") == "non_compliant" 
            for r in rule_results.values() 
            if r.get("status") != "not_evaluated"
        )
        
        if all_compliant and total_rules > 5:
            issues.append("All evaluated rules marked as compliant (suspicious)")
            severity = max(severity, CriticSeverity.WARNING)
        elif all_non_compliant and total_rules > 5:
            issues.append("All evaluated rules marked as non-compliant (suspicious)")
            severity = max(severity, CriticSeverity.WARNING)
        
        # Calculate quality score
        quality_score = self._calculate_quality_score(metrics)
        metrics["quality_score"] = f"{quality_score:.1%}"
        
        # Determine if valid and should retry
        is_valid = quality_score >= 0.6
        should_retry = (
            quality_score < 0.5 and 
            state.get("rule_compliance_critic_attempts", 0) < self.max_retries
        )
        
        if quality_score < 0.4:
            severity = CriticSeverity.CRITICAL
        elif quality_score < 0.6:
            severity = max(severity, CriticSeverity.ERROR)
        
        return ValidationResult(
            is_valid=is_valid,
            severity=severity,
            issues=issues,
            recommendations=recommendations,
            metrics=metrics,
            should_retry=should_retry,
            retry_params=self._get_retry_params(not_evaluated, no_evidence) if should_retry else None
        )
    
    def _has_conflicting_evidence(self, result: Dict[str, Any]) -> bool:
        """Check if a rule result has conflicting evidence"""
        evidence = result.get("evidence", [])
        if len(evidence) < 2:
            return False
        
        # Look for both positive and negative indicators
        has_compliant = any(
            "compliant" in str(e).lower() or 
            "satisfies" in str(e).lower() or
            "meets" in str(e).lower()
            for e in evidence
        )
        has_non_compliant = any(
            "non-compliant" in str(e).lower() or 
            "violates" in str(e).lower() or
            "fails" in str(e).lower()
            for e in evidence
        )
        
        return has_compliant and has_non_compliant
    
    def _calculate_quality_score(self, metrics: Dict[str, Any]) -> float:
        """Calculate overall quality score for rule compliance"""
        scores = {
            "evaluation_rate": 1.0 - metrics.get("not_evaluated_ratio", 0),
            "evidence_quality": 1.0 - (metrics.get("no_evidence_count", 0) / max(metrics.get("total_rules", 1), 1)),
            "consistency": 1.0 - (metrics.get("conflicting_count", 0) / max(metrics.get("total_rules", 1), 1)),
            "critical_coverage": 1.0 - (metrics.get("critical_missing", 0) / len(self.critical_rules))
        }
        
        # Weighted average
        weights = {
            "evaluation_rate": 0.3,
            "evidence_quality": 0.25,
            "consistency": 0.25,
            "critical_coverage": 0.2
        }
        
        total_score = sum(scores[key] * weights[key] for key in scores)
        return total_score
    
    def _get_retry_params(self, not_evaluated: List[str], no_evidence: List[str]) -> Dict[str, Any]:
        """Get parameters for retry based on issues found"""
        params = {"rule_compliance_mode": "enhanced"}
        
        if not_evaluated:
            params["retry_unevaluated_rules"] = not_evaluated[:10]  # Limit to top 10
            params["use_retrieval_fallback"] = True
        
        if no_evidence:
            params["expand_evidence_search"] = True
            params["evidence_context_window"] = 3  # Sentences before/after
        
        return params

# Create node and condition functions for LangGraph
rule_compliance_critic_node = create_critic_node(RuleComplianceCritic)

def should_rerun_rule_compliance(state: Dict[str, Any]) -> str:
    """Condition to determine if rule compliance should be rerun"""
    critic = RuleComplianceCritic()
    
    if not critic.enabled:
        return "continue"
    
    # If no rules file provided, skip
    if not state.get("rules_file"):
        return "continue"
    
    validation_key = "rule_compliance_validation_result"
    if validation_key not in state:
        return "continue"
    
    validation_data = state[validation_key]
    attempts = state.get("rule_compliance_critic_attempts", 0)
    
    # Only retry for critical or error severity
    if not validation_data["is_valid"] and validation_data["severity"] in ["error", "critical"]:
        if attempts < critic.max_retries:
            return "retry"
    
    return "continue"