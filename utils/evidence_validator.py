"""
Evidence Validator
Validates evidence and citations for rule compliance results
"""

import re
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
import logging

from utils.rule_manager import Rule, EvidenceRequirements
from utils.citation_manager import Citation, citation_manager
from utils.deterministic_checker import DeterministicResult
from utils.llm_judge import LLMJudgment

logger = logging.getLogger(__name__)


@dataclass
class EvidenceValidationResult:
    """Result of evidence validation"""
    is_valid: bool
    rule_id: str
    status: str
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    citation_count: int = 0
    valid_citations: int = 0
    missing_anchors: int = 0
    confidence: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "is_valid": self.is_valid,
            "rule_id": self.rule_id,
            "status": self.status,
            "errors": self.errors,
            "warnings": self.warnings,
            "evidence_stats": {
                "citation_count": self.citation_count,
                "valid_citations": self.valid_citations,
                "missing_anchors": self.missing_anchors
            },
            "confidence": self.confidence
        }


@dataclass
class ComplianceResult:
    """Combined result of rule compliance checking"""
    rule_id: str
    status: str  # compliant, non_compliant, not_applicable, unknown
    rationale: str
    citations: List[Citation] = field(default_factory=list)
    deterministic_result: Optional[DeterministicResult] = None
    llm_judgment: Optional[LLMJudgment] = None
    validation: Optional[EvidenceValidationResult] = None
    confidence: float = 0.0
    attribution: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "rule_id": self.rule_id,
            "status": self.status,
            "rationale": self.rationale,
            "citations": [c.to_dict() for c in self.citations],
            "confidence": self.confidence,
            "attribution": self.attribution,
            "validation": self.validation.to_dict() if self.validation else None,
            "deterministic": self.deterministic_result.to_dict() if self.deterministic_result else None,
            "llm": self.llm_judgment.to_dict() if self.llm_judgment else None
        }


class EvidenceValidator:
    """Validates evidence for compliance results"""
    
    def __init__(self, strict_mode: bool = True):
        """
        Initialize evidence validator
        
        Args:
            strict_mode: Whether to enforce strict validation
        """
        self.strict_mode = strict_mode
        self.stats = {
            "total_validations": 0,
            "valid_results": 0,
            "invalid_results": 0,
            "missing_citations": 0,
            "invalid_anchors": 0
        }
    
    def validate_compliance_result(
        self,
        result: ComplianceResult,
        rule: Rule,
        document_text: str,
        page_map: Optional[Dict[int, int]] = None
    ) -> EvidenceValidationResult:
        """
        Validate compliance result evidence
        
        Args:
            result: Compliance result to validate
            rule: Rule being evaluated
            document_text: Original document
            page_map: Page mapping
            
        Returns:
            Validation result
        """
        self.stats["total_validations"] += 1
        
        validation = EvidenceValidationResult(
            is_valid=True,
            rule_id=result.rule_id,
            status=result.status
        )
        
        # Check citation requirements
        validation = self._check_citation_requirements(
            result,
            rule.evidence_requirements,
            validation
        )
        
        # Validate individual citations
        if result.citations:
            validation = self._validate_citations(
                result.citations,
                document_text,
                page_map,
                rule.evidence_requirements,
                validation
            )
        
        # Check page anchors
        validation = self._check_page_anchors(result.citations, validation)
        
        # Validate evidence completeness
        validation = self._check_evidence_completeness(
            result,
            rule.evidence_requirements,
            validation
        )
        
        # Calculate confidence
        validation.confidence = self._calculate_evidence_confidence(validation)
        
        # Update statistics
        if validation.is_valid:
            self.stats["valid_results"] += 1
        else:
            self.stats["invalid_results"] += 1
        
        # Attach to result
        result.validation = validation
        
        return validation
    
    def _check_citation_requirements(
        self,
        result: ComplianceResult,
        requirements: EvidenceRequirements,
        validation: EvidenceValidationResult
    ) -> EvidenceValidationResult:
        """Check if citation requirements are met"""
        
        validation.citation_count = len(result.citations)
        
        # Check minimum citations
        if result.status != "unknown":
            if validation.citation_count < requirements.min_citations:
                error = f"Insufficient citations: found {validation.citation_count}, required {requirements.min_citations}"
                validation.errors.append(error)
                validation.is_valid = False
                self.stats["missing_citations"] += 1
        
        # Exception: unknown status doesn't require citations
        elif result.status == "unknown" and validation.citation_count == 0:
            # This is acceptable
            pass
        
        return validation
    
    def _validate_citations(
        self,
        citations: List[Citation],
        document_text: str,
        page_map: Optional[Dict[int, int]],
        requirements: EvidenceRequirements,
        validation: EvidenceValidationResult
    ) -> EvidenceValidationResult:
        """Validate individual citations"""
        
        for citation in citations:
            # Validate citation exists in document
            citation_validation = citation_manager.validate_citation(
                citation,
                document_text,
                page_map,
                require_exact=requirements.require_exact_quotes
            )
            
            if citation_validation.is_valid:
                validation.valid_citations += 1
            else:
                for error in citation_validation.errors:
                    validation.errors.append(f"Citation error: {error}")
                validation.is_valid = False
            
            # Add warnings
            for warning in citation_validation.warnings:
                validation.warnings.append(warning)
            
            # Check citation distance if specified
            if requirements.max_citation_distance:
                # This would require knowing where the rule content is expected
                # For now, just add a warning if citation is very far in document
                if citation.start_char > len(document_text) * 0.8:
                    validation.warnings.append(
                        f"Citation appears late in document (position {citation.start_char})"
                    )
        
        return validation
    
    def _check_page_anchors(
        self,
        citations: List[Citation],
        validation: EvidenceValidationResult
    ) -> EvidenceValidationResult:
        """Check page anchor requirements"""
        
        for citation in citations:
            # Check anchor format
            if not citation.anchor or not re.match(r'^\[\[page=\d+\]\]$', citation.anchor):
                validation.missing_anchors += 1
                validation.errors.append(f"Invalid or missing page anchor: {citation.anchor}")
                validation.is_valid = False
                self.stats["invalid_anchors"] += 1
            
            # Check page number validity
            if citation.page <= 0:
                validation.errors.append(f"Invalid page number: {citation.page}")
                validation.is_valid = False
        
        return validation
    
    def _check_evidence_completeness(
        self,
        result: ComplianceResult,
        requirements: EvidenceRequirements,
        validation: EvidenceValidationResult
    ) -> EvidenceValidationResult:
        """Check evidence completeness"""
        
        # No verdict without citations (except unknown)
        if result.status in ["compliant", "non_compliant", "not_applicable"]:
            if not result.citations and self.strict_mode:
                validation.errors.append(
                    f"No evidence provided for {result.status} verdict"
                )
                validation.is_valid = False
        
        # Check if rationale is substantive
        if not result.rationale or len(result.rationale) < 20:
            validation.warnings.append("Rationale is too brief or missing")
        
        # Check attribution
        if not result.attribution:
            validation.warnings.append("Missing attribution information")
        
        return validation
    
    def _calculate_evidence_confidence(
        self,
        validation: EvidenceValidationResult
    ) -> float:
        """Calculate confidence based on evidence quality"""
        
        if not validation.is_valid:
            return 0.0
        
        confidence_factors = []
        
        # Citation validity ratio
        if validation.citation_count > 0:
            citation_ratio = validation.valid_citations / validation.citation_count
            confidence_factors.append(citation_ratio)
        
        # Page anchor completeness
        if validation.citation_count > 0:
            anchor_ratio = 1.0 - (validation.missing_anchors / validation.citation_count)
            confidence_factors.append(anchor_ratio)
        
        # Error/warning impact
        error_penalty = len(validation.errors) * 0.1
        warning_penalty = len(validation.warnings) * 0.05
        quality_score = max(0, 1.0 - error_penalty - warning_penalty)
        confidence_factors.append(quality_score)
        
        if confidence_factors:
            return sum(confidence_factors) / len(confidence_factors)
        
        return 0.5  # Default moderate confidence
    
    def validate_batch(
        self,
        results: List[ComplianceResult],
        rules: Dict[str, Rule],
        document_text: str,
        page_map: Optional[Dict[int, int]] = None
    ) -> List[EvidenceValidationResult]:
        """
        Validate multiple compliance results
        
        Args:
            results: Results to validate
            rules: Dictionary of rules by ID
            document_text: Document text
            page_map: Page mapping
            
        Returns:
            List of validation results
        """
        validations = []
        
        for result in results:
            rule = rules.get(result.rule_id)
            if not rule:
                logger.warning(f"Rule {result.rule_id} not found for validation")
                continue
            
            validation = self.validate_compliance_result(
                result,
                rule,
                document_text,
                page_map
            )
            
            validations.append(validation)
        
        return validations
    
    def enforce_evidence_requirements(
        self,
        result: ComplianceResult,
        rule: Rule
    ) -> ComplianceResult:
        """
        Enforce evidence requirements on result
        
        Args:
            result: Result to enforce
            rule: Rule being evaluated
            
        Returns:
            Modified result with enforcement applied
        """
        # If no citations and not unknown, change to unknown
        if result.status != "unknown" and not result.citations:
            if self.strict_mode:
                result.status = "unknown"
                result.rationale = f"Changed to unknown due to lack of evidence. Original: {result.rationale}"
                result.confidence = 0.0
        
        # If missing required page anchors, reduce confidence
        missing_anchors = sum(
            1 for c in result.citations
            if not c.anchor or not re.match(r'^\[\[page=\d+\]\]$', c.anchor)
        )
        
        if missing_anchors > 0 and rule.evidence_requirements.require_page_anchors:
            result.confidence *= 0.5  # Halve confidence for missing anchors
        
        return result
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get validation statistics"""
        total = self.stats["total_validations"]
        if total == 0:
            return self.stats
        
        return {
            **self.stats,
            "validity_rate": self.stats["valid_results"] / total,
            "citation_missing_rate": self.stats["missing_citations"] / total,
            "anchor_invalid_rate": self.stats["invalid_anchors"] / total
        }


# Global evidence validator instance
evidence_validator = EvidenceValidator()


def validate_evidence(
    result: ComplianceResult,
    rule: Rule,
    document_text: str,
    page_map: Optional[Dict[int, int]] = None
) -> EvidenceValidationResult:
    """
    Convenience function to validate evidence
    
    Args:
        result: Compliance result
        rule: Rule being evaluated
        document_text: Document text
        page_map: Page mapping
        
    Returns:
        Validation result
    """
    return evidence_validator.validate_compliance_result(
        result,
        rule,
        document_text,
        page_map
    )