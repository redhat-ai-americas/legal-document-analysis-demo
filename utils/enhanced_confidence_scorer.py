"""
Enhanced Confidence Scorer with Method Tracking

Tracks HOW confidence was calculated and provides detailed attribution
for each confidence score.
"""

import re
from typing import Dict, Any, List, Optional, Tuple
from enum import Enum


class ConfidenceMethod(Enum):
    """Methods used to calculate confidence."""
    LOGPROBS = "logprobs"  # LLM logprobs-based
    HEURISTIC_OVERLAP = "heuristic_word_overlap"  # Word overlap between answer and source
    HEURISTIC_COMPLETENESS = "heuristic_completeness"  # Answer length/quality
    HEURISTIC_SPECIFICITY = "heuristic_specificity"  # Presence of specific entities
    HEURISTIC_COMBINED = "heuristic_combined"  # Multiple heuristics
    DETERMINISTIC = "deterministic"  # Fixed confidence (100%)
    NO_CLAUSES = "no_clauses_found"  # No relevant text (100%)
    MODEL_PROVIDED = "model_provided"  # LLM provided its own confidence
    ERROR = "error"  # Error occurred (0%)


class EnhancedConfidenceScorer:
    """
    Enhanced confidence scoring with detailed method tracking.
    """
    
    def __init__(self):
        self.last_calculation = None
    
    def _tokenize(self, text: str) -> List[str]:
        """Tokenize text for analysis."""
        text = (text or "").lower()
        return re.findall(r"[a-z0-9]+", text)
    
    def _word_overlap_score(self, a: str, b: str) -> Tuple[float, str]:
        """Calculate word overlap and return score with details."""
        a_tokens = set(self._tokenize(a))
        b_tokens = set(self._tokenize(b))
        if not a_tokens or not b_tokens:
            return 0.0, "No tokens to compare"
        
        intersection = a_tokens & b_tokens
        inter_count = len(intersection)
        denom = max(len(a_tokens), 1)
        score = min(1.0, inter_count / denom)
        
        details = f"Found {inter_count}/{len(a_tokens)} answer words in source"
        if intersection and len(intersection) <= 5:
            details += f" (matched: {', '.join(list(intersection)[:5])})"
        
        return score, details
    
    def _specificity_score(self, text: str) -> Tuple[float, List[str]]:
        """Calculate specificity score and return what was found."""
        findings = []
        score = 0.0
        
        # Check for numbers
        numbers = re.findall(r"\b\d+\b", text)
        if numbers:
            score += 0.3
            findings.append(f"numbers: {', '.join(numbers[:3])}")
        
        # Check for dates
        date_patterns = [
            r"\b\d{4}-\d{2}-\d{2}\b",  # YYYY-MM-DD
            r"\b\d{1,2}/\d{1,2}/\d{2,4}\b",  # MM/DD/YYYY
            r"\b\d{1,2}\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{2,4}\b"
        ]
        for pattern in date_patterns:
            dates = re.findall(pattern, text, re.IGNORECASE)
            if dates:
                score += 0.3
                findings.append(f"dates: {dates[0]}")
                break
        
        # Check for proper nouns (entities)
        proper_nouns = re.findall(r"\b[A-Z][a-zA-Z]{2,}\b", text)
        if proper_nouns:
            score += min(0.4, len(proper_nouns) * 0.05)
            findings.append(f"entities: {', '.join(proper_nouns[:3])}")
        
        return min(1.0, score), findings
    
    def _completeness_score(self, text: str) -> Tuple[float, str]:
        """Score completeness based on length."""
        length = len((text or "").strip())
        
        if length == 0:
            return 0.0, "Empty answer"
        elif length < 10:
            return 0.2, f"Very short ({length} chars)"
        elif length < 30:
            return 0.4, f"Short answer ({length} chars)"
        elif length < 120:
            return 0.8, f"Good length ({length} chars)"
        elif length < 400:
            return 1.0, f"Detailed answer ({length} chars)"
        else:
            return 0.7, f"Very long ({length} chars, may be verbose)"
    
    def score_from_logprobs(self, logprobs: List[float]) -> Dict[str, Any]:
        """
        Calculate confidence from LLM logprobs.
        """
        if not logprobs:
            return self._create_result(0.5, ConfidenceMethod.ERROR, "No logprobs available")
        
        # Convert average logprob to confidence
        avg_logprob = sum(logprobs) / len(logprobs)
        
        # Logprobs are typically negative values (e.g., -0.5 to -5)
        # Use a scaled sigmoid transformation for realistic confidence scores
        # Map avg_logprob of -5 -> ~50%, -2 -> ~75%, -0.5 -> ~90%
        # Formula: confidence = 1 / (1 + exp(-(avg_logprob + 2.5)))
        # This shifts the midpoint to -2.5 and provides a good range
        
        # Alternative simpler approach: clamp and scale
        # Map -5 to 0.5, -1 to 0.9, 0 to 0.95
        if avg_logprob >= 0:
            prob = 0.95  # Very confident
        elif avg_logprob <= -5:
            prob = 0.5  # Low confidence
        else:
            # Linear interpolation between -5 and 0
            # -5 maps to 0.5, 0 maps to 0.95
            prob = 0.5 + (avg_logprob + 5) * 0.09  # 0.09 = (0.95-0.5)/5
        confidence = min(1.0, max(0.0, prob))
        
        details = {
            "avg_logprob": round(avg_logprob, 4),
            "token_count": len(logprobs),
            "raw_probability": round(prob, 4)
        }
        
        return self._create_result(
            confidence,
            ConfidenceMethod.LOGPROBS,
            f"Calculated from {len(logprobs)} token logprobs",
            details
        )
    
    def score_extraction_confidence(self, question: str, answer: str, 
                                  source_text: str = "",
                                  logprobs: Optional[List[float]] = None,
                                  model_confidence: Optional[float] = None) -> Dict[str, Any]:
        """
        Enhanced extraction confidence with method tracking.
        """
        # Priority 1: Use logprobs if available
        if logprobs:
            return self.score_from_logprobs(logprobs)
        
        # Priority 2: Use model-provided confidence
        if model_confidence is not None:
            return self._create_result(
                model_confidence,
                ConfidenceMethod.MODEL_PROVIDED,
                "Confidence provided by model"
            )
        
        # Priority 3: Heuristic scoring
        completeness, completeness_detail = self._completeness_score(answer)
        support, support_detail = self._word_overlap_score(answer, source_text)
        specificity, specificity_findings = self._specificity_score(answer)
        
        # Weighted combination
        weights = {
            'completeness': 0.3,
            'support': 0.4,
            'specificity': 0.3
        }
        
        overall = (
            weights['completeness'] * completeness +
            weights['support'] * support +
            weights['specificity'] * specificity
        )
        
        details = {
            'completeness': {
                'score': round(completeness, 2),
                'detail': completeness_detail
            },
            'source_support': {
                'score': round(support, 2),
                'detail': support_detail
            },
            'specificity': {
                'score': round(specificity, 2),
                'findings': specificity_findings
            },
            'weights': weights
        }
        
        reasoning = f"Heuristic: {completeness_detail}, {support_detail}"
        if specificity_findings:
            reasoning += f", found: {', '.join(specificity_findings)}"
        
        return self._create_result(
            overall,
            ConfidenceMethod.HEURISTIC_COMBINED,
            reasoning,
            details
        )
    
    def score_deterministic(self) -> Dict[str, Any]:
        """Score for deterministic fields."""
        return self._create_result(
            1.0,
            ConfidenceMethod.DETERMINISTIC,
            "Pre-defined field with 100% confidence"
        )
    
    def score_no_clauses_found(self, searched_terms: List[str]) -> Dict[str, Any]:
        """Score for when no relevant clauses were found."""
        return self._create_result(
            1.0,
            ConfidenceMethod.NO_CLAUSES,
            f"No clauses found for terms: {', '.join(searched_terms)}"
        )
    
    def score_error(self, error_msg: str) -> Dict[str, Any]:
        """Score for error cases."""
        return self._create_result(
            0.0,
            ConfidenceMethod.ERROR,
            f"Error: {error_msg}"
        )
    
    def _create_result(self, confidence: float, method: ConfidenceMethod, 
                      reasoning: str, details: Optional[Dict] = None) -> Dict[str, Any]:
        """Create a standardized confidence result."""
        result = {
            "overall_confidence": round(confidence * 100, 1),
            "confidence_method": method.value,
            "reasoning": reasoning,
            "needs_review": confidence < 0.6,
            "concerns": []
        }
        
        if details:
            result["calculation_details"] = details
        
        if confidence < 0.3:
            result["concerns"].append("Very low confidence - manual review required")
        elif confidence < 0.6:
            result["concerns"].append("Low confidence - review recommended")
        
        # Store for debugging
        self.last_calculation = result
        
        return result
    
    def get_method_description(self, method: str) -> str:
        """Get human-readable description of confidence method."""
        descriptions = {
            "logprobs": "Calculated from LLM token probabilities",
            "heuristic_word_overlap": "Based on word overlap between answer and source",
            "heuristic_completeness": "Based on answer length and structure",
            "heuristic_specificity": "Based on presence of specific entities/dates/numbers",
            "heuristic_combined": "Combined heuristic analysis",
            "deterministic": "Pre-defined field (100% confidence)",
            "no_clauses_found": "No relevant text found (definitive)",
            "model_provided": "Confidence score provided by the model",
            "error": "Error occurred during processing"
        }
        return descriptions.get(method, "Unknown method")


# Global enhanced confidence scorer
enhanced_confidence_scorer = EnhancedConfidenceScorer()