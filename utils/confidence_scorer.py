"""
Confidence scoring utility (local heuristic, no external LLM calls).
Provides confidence evaluation for various extraction types using
lightweight text heuristics so we can run Granite-only.
"""

import re
from typing import Dict, Any, List

class ConfidenceScorer:
    """
    Confidence scoring system using simple heuristics:
    - Token overlap between answer and source_text (source_support)
    - Answer completeness (length-based)
    - Specificity heuristics (numbers, dates, entities)
    """

    def _tokenize(self, text: str) -> List[str]:
        text = (text or "").lower()
        return re.findall(r"[a-z0-9]+", text)

    def _word_overlap_score(self, a: str, b: str) -> float:
        a_tokens = set(self._tokenize(a))
        b_tokens = set(self._tokenize(b))
        if not a_tokens or not b_tokens:
            return 0.0
        inter = len(a_tokens & b_tokens)
        denom = max(len(a_tokens), 1)
        return min(1.0, inter / denom)

    def _specificity_score(self, text: str) -> float:
        # Heuristics: presence of numbers, dates-like patterns, proper nouns (capitalized words)
        has_number = bool(re.search(r"\d", text))
        has_date = bool(re.search(r"\b(\d{1,2}\s+[A-Za-z]{3,9}\s+\d{2,4}|\d{4}-\d{2}-\d{2})\b", text))
        proper_nouns = re.findall(r"\b[A-Z][a-zA-Z]{2,}\b", text)
        score = 0.0
        score += 0.3 if has_number else 0.0
        score += 0.3 if has_date else 0.0
        score += min(0.4, len(proper_nouns) * 0.05)
        return min(1.0, score)
    
    def _completeness_score(self, text: str) -> float:
        # Short answers are less complete; very long also penalized
        length = len((text or "").strip())
        if length == 0:
            return 0.0
        if length < 30:
            return 0.4
        if length < 120:
            return 0.8
        if length < 400:
            return 1.0
        return 0.7
    
    def score_classification_confidence(self, sentence: str, classifications: List[str], 
                                      classification_context: str = "") -> Dict[str, Any]:
        """
        Score confidence for sentence classification results.
        """
        clarity = self._completeness_score(sentence)
        relevance = self._word_overlap_score(sentence, classification_context)
        accuracy = min(1.0, len(classifications) / 5.0) if classifications else 0.2
        overall = (0.4 * relevance + 0.4 * clarity + 0.2 * accuracy) * 100
        return {
            "overall_confidence": round(overall, 1),
            "text_clarity": round(clarity * 100, 1),
            "classification_accuracy": round(accuracy * 100, 1),
            "context_relevance": round(relevance * 100, 1),
            "reasoning": "Heuristic scoring based on overlap, clarity, and class count",
            "concerns": []
        }
    
    def score_extraction_confidence(self, question: str, answer: str, 
                                  source_text: str = "") -> Dict[str, Any]:
        """
        Score confidence for question-answer extraction results.
        """
        completeness = self._completeness_score(answer)
        support = self._word_overlap_score(answer, source_text)
        specificity = self._specificity_score(answer)
        factual = min(1.0, (support * 0.7 + specificity * 0.3))
        overall = (0.4 * support + 0.3 * specificity + 0.2 * completeness + 0.1 * factual) * 100
        needs_review = overall < 60
        return {
            "overall_confidence": round(overall, 1),
            "answer_completeness": round(completeness * 100, 1),
            "source_support": round(support * 100, 1),
            "answer_specificity": round(specificity * 100, 1),
            "factual_accuracy": round(factual * 100, 1),
            "reasoning": "Heuristic scoring based on overlap, specificity, and length",
            "concerns": [],
            "needs_review": needs_review
        }
    
    def score_risk_assessment(self, clause_text: str, risk_indicators: List[str]) -> Dict[str, Any]:
        """
        Score risk level and confidence for contract clauses.
        """
        text = clause_text or ""
        # Simple risk heuristic: if many risk indicators present, higher risk
        hits = 0
        for ind in (risk_indicators or []):
            try:
                if ind and re.search(re.escape(str(ind)), text, re.IGNORECASE):
                    hits += 1
            except re.error:
                continue
        ratio = min(1.0, hits / max(1, len(risk_indicators or []))) if risk_indicators else 0.3
        level = "Low"
        if ratio >= 0.75:
            level = "High"
        elif ratio >= 0.5:
            level = "Medium"
        confidence = round((0.5 + ratio * 0.5) * 100, 1)
        return {
            "risk_level": level,
            "risk_confidence": confidence,
            "business_impact": "Medium" if level in ("Medium", "High") else "Low",
            "risk_factors": risk_indicators or [],
            "mitigation_urgency": "Immediate" if level == "High" else ("Soon" if level == "Medium" else "Low"),
            "reasoning": "Heuristic based on indicator hits"
        }
    
    def calculate_overall_document_confidence(self, 
                                            classification_scores: List[float],
                                            extraction_scores: List[float],
                                            processing_metrics: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculate overall document analysis confidence based on component scores.
        """
        if not classification_scores and not extraction_scores:
            return {
                "overall_confidence": 0,
                "confidence_grade": "F",
                "reliability": "Very Low",
                "needs_manual_review": True,
                "reasoning": "No valid scores available"
            }
        
        # Calculate weighted average
        all_scores = classification_scores + extraction_scores
        avg_score = sum(all_scores) / len(all_scores) if all_scores else 0
        
        # Adjust for processing issues
        processing_penalty = 0
        if processing_metrics.get("fallback_strategies_used"):
            processing_penalty += 10
        if processing_metrics.get("api_failures", 0) > 0:
            processing_penalty += 15
        if processing_metrics.get("partial_failures", 0) > 0:
            processing_penalty += 5
        
        final_score = max(0, avg_score - processing_penalty)
        
        # Determine grade and reliability
        if final_score >= 90:
            grade, reliability = "A", "Very High"
        elif final_score >= 80:
            grade, reliability = "B", "High"
        elif final_score >= 70:
            grade, reliability = "C", "Medium"
        elif final_score >= 60:
            grade, reliability = "D", "Low"
        else:
            grade, reliability = "F", "Very Low"
        
        needs_review = final_score < 70 or processing_penalty > 10
        
        return {
            "overall_confidence": final_score,
            "confidence_grade": grade,
            "reliability": reliability,
            "needs_manual_review": needs_review,
            "component_scores": {
                "classification_avg": sum(classification_scores) / len(classification_scores) if classification_scores else 0,
                "extraction_avg": sum(extraction_scores) / len(extraction_scores) if extraction_scores else 0,
                "processing_penalty": processing_penalty
            },
            "reasoning": f"Based on {len(all_scores)} component assessments with {processing_penalty} penalty points"
        }


# Global instance for easy import
confidence_scorer = ConfidenceScorer()