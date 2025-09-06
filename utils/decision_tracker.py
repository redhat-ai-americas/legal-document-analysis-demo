"""
Decision Tracking System for Contract Analysis Workflow

Tracks how each decision was made, by which component, and provides clear attribution
for all answers in the questionnaire processing pipeline.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
from enum import Enum


class DecisionMethod(Enum):
    """Enumeration of decision-making methods."""
    DETERMINISTIC = "deterministic"  # Pre-defined field (document name, etc.)
    NO_RELEVANT_CLAUSES = "no_relevant_clauses"  # No sentences found for this term
    LLM_GRANITE = "llm_granite"  # Granite model made the decision
    LLM_MIXTRAL = "llm_mixtral"  # Mixtral model made the decision
    LLM_OLLAMA = "llm_ollama"  # Ollama model made the decision
    LLM_TUNED = "llm_tuned"  # Fine-tuned model made the decision
    CLASSIFICATION_BASED = "classification_based"  # Based on sentence classification
    RULE_BASED = "rule_based"  # Based on compliance rules
    REFERENCE_COMPARISON = "reference_comparison"  # Based on reference doc comparison
    ERROR = "error"  # Error occurred during processing
    MANUAL_REQUIRED = "manual_required"  # Requires manual review


class DecisionAttribution:
    """Tracks attribution for a single decision."""
    
    def __init__(self, question_id: str, question_text: str):
        self.question_id = question_id
        self.question_text = question_text
        self.timestamp = datetime.now().isoformat()
        
        # Core decision info
        self.method: DecisionMethod = None
        self.answer: str = None
        self.confidence: float = 0.0
        
        # Attribution details
        self.llm_used: Optional[str] = None  # Which LLM was used
        self.llm_prompt: Optional[str] = None  # What prompt was sent
        self.llm_raw_response: Optional[str] = None  # Raw LLM response
        self.llm_reasoning: Optional[str] = None  # LLM's reasoning
        
        # Supporting evidence
        self.source_sentences: List[Dict[str, Any]] = []
        self.classified_terms: List[str] = []
        self.relevant_rules: List[str] = []
        self.reference_deviation: Optional[str] = None
        
        # Processing metadata
        self.processing_node: Optional[str] = None  # Which node made the decision
        self.processing_time_ms: Optional[float] = None
        self.token_count: Optional[int] = None
        self.api_calls_made: int = 0
        
        # Decision rationale
        self.rationale: str = ""
        self.warnings: List[str] = []
        self.requires_review: bool = False
        
    def set_deterministic(self, answer: str, source: str):
        """Mark as deterministic decision."""
        self.method = DecisionMethod.DETERMINISTIC
        self.answer = answer
        self.confidence = 1.0
        self.rationale = f"Deterministic field extracted from {source}"
        self.processing_node = "questionnaire_processor"
        
    def set_no_clauses_found(self, searched_terms: List[str]):
        """Mark as no relevant clauses found."""
        self.method = DecisionMethod.NO_RELEVANT_CLAUSES
        self.answer = "Not specified in the contract"
        self.confidence = 1.0
        self.classified_terms = searched_terms
        self.rationale = f"No clauses found containing terms: {', '.join(searched_terms)}"
        self.processing_node = "classification_based_filtering"
        
    def set_llm_decision(self, 
                        llm_name: str,
                        answer: str,
                        confidence: float,
                        prompt: str,
                        raw_response: str,
                        reasoning: Optional[str] = None,
                        token_count: Optional[int] = None):
        """Mark as LLM-based decision."""
        # Set method based on LLM type
        if "granite" in llm_name.lower():
            self.method = DecisionMethod.LLM_GRANITE
        elif "mixtral" in llm_name.lower():
            self.method = DecisionMethod.LLM_MIXTRAL
        elif "ollama" in llm_name.lower():
            self.method = DecisionMethod.LLM_OLLAMA
        elif "tuned" in llm_name.lower():
            self.method = DecisionMethod.LLM_TUNED
        else:
            self.method = DecisionMethod.LLM_GRANITE  # Default
            
        self.llm_used = llm_name
        self.answer = answer
        self.confidence = confidence
        self.llm_prompt = prompt[:500] if len(prompt) > 500 else prompt  # Truncate long prompts
        self.llm_raw_response = raw_response[:1000] if len(raw_response) > 1000 else raw_response
        self.llm_reasoning = reasoning
        self.token_count = token_count
        self.api_calls_made = 1
        self.processing_node = "questionnaire_processor"
        
        # Generate rationale
        if confidence < 0.6:
            self.requires_review = True
            self.warnings.append(f"Low confidence ({confidence:.2f})")
            
        self.rationale = f"Answer determined by {llm_name} with {confidence:.1f}% confidence"
        
    def set_classification_based(self, answer: str, classified_sentences: List[Dict]):
        """Mark as classification-based decision."""
        self.method = DecisionMethod.CLASSIFICATION_BASED
        self.answer = answer
        self.source_sentences = classified_sentences
        self.classified_terms = list(set(
            term for sent in classified_sentences 
            for term in sent.get('classes', [])
        ))
        self.confidence = 0.8  # Classification confidence
        self.processing_node = "document_classifier"
        self.rationale = f"Based on classification of {len(classified_sentences)} sentences with terms: {', '.join(self.classified_terms[:5])}"
        
    def set_error(self, error_message: str):
        """Mark as error during processing."""
        self.method = DecisionMethod.ERROR
        self.answer = "Error: Could not process"
        self.confidence = 0.0
        self.requires_review = True
        self.warnings.append(error_message)
        self.rationale = f"Processing failed: {error_message}"
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "question_id": self.question_id,
            "question_text": self.question_text,
            "timestamp": self.timestamp,
            "answer": self.answer,
            "confidence": self.confidence,
            "method": self.method.value if self.method else None,
            "attribution": {
                "llm_used": self.llm_used,
                "llm_reasoning": self.llm_reasoning,
                "processing_node": self.processing_node,
                "rationale": self.rationale
            },
            "evidence": {
                "source_sentences_count": len(self.source_sentences),
                "classified_terms": self.classified_terms,
                "relevant_rules": self.relevant_rules,
                "reference_deviation": self.reference_deviation
            },
            "metadata": {
                "processing_time_ms": self.processing_time_ms,
                "token_count": self.token_count,
                "api_calls": self.api_calls_made,
                "requires_review": self.requires_review,
                "warnings": self.warnings
            }
        }
    
    def get_summary(self) -> str:
        """Get a human-readable summary of the decision."""
        if self.method == DecisionMethod.DETERMINISTIC:
            return f"✅ Deterministic: {self.answer}"
        elif self.method == DecisionMethod.NO_RELEVANT_CLAUSES:
            return f"⚠️ No clauses found (searched: {', '.join(self.classified_terms[:3])})"
        elif self.method in [DecisionMethod.LLM_GRANITE, DecisionMethod.LLM_MIXTRAL, DecisionMethod.LLM_OLLAMA]:
            return f"🤖 {self.llm_used}: {self.answer} (conf: {self.confidence:.1f}%)"
        elif self.method == DecisionMethod.ERROR:
            return f"❌ Error: {self.warnings[0] if self.warnings else 'Unknown error'}"
        else:
            return f"📊 {self.method.value}: {self.answer}"


class DecisionTracker:
    """Tracks all decisions made during contract analysis."""
    
    def __init__(self):
        self.decisions: Dict[str, DecisionAttribution] = {}
        self.start_time = datetime.now()
        self.statistics = {
            "total_questions": 0,
            "deterministic_answers": 0,
            "llm_answers": 0,
            "no_clauses_found": 0,
            "errors": 0,
            "low_confidence": 0,
            "requires_review": 0,
            "llm_calls_by_model": {}
        }
        
    def track_decision(self, attribution: DecisionAttribution):
        """Track a decision attribution."""
        self.decisions[attribution.question_id] = attribution
        self.update_statistics(attribution)
        
    def update_statistics(self, attribution: DecisionAttribution):
        """Update running statistics."""
        self.statistics["total_questions"] += 1
        
        if attribution.method == DecisionMethod.DETERMINISTIC:
            self.statistics["deterministic_answers"] += 1
        elif attribution.method == DecisionMethod.NO_RELEVANT_CLAUSES:
            self.statistics["no_clauses_found"] += 1
        elif attribution.method == DecisionMethod.ERROR:
            self.statistics["errors"] += 1
        elif attribution.method in [DecisionMethod.LLM_GRANITE, DecisionMethod.LLM_MIXTRAL, 
                                 DecisionMethod.LLM_OLLAMA, DecisionMethod.LLM_TUNED]:
            self.statistics["llm_answers"] += 1
            model = attribution.llm_used or "unknown"
            self.statistics["llm_calls_by_model"][model] = \
                self.statistics["llm_calls_by_model"].get(model, 0) + 1
                
        if attribution.confidence < 0.6:
            self.statistics["low_confidence"] += 1
            
        if attribution.requires_review:
            self.statistics["requires_review"] += 1
            
    def get_decision(self, question_id: str) -> Optional[DecisionAttribution]:
        """Get a specific decision attribution."""
        return self.decisions.get(question_id)
    
    def get_summary_report(self) -> Dict[str, Any]:
        """Generate a summary report of all decisions."""
        duration = (datetime.now() - self.start_time).total_seconds()
        
        return {
            "execution_time_seconds": duration,
            "statistics": self.statistics,
            "decision_methods": {
                method.value: sum(1 for d in self.decisions.values() if d.method == method)
                for method in DecisionMethod
            },
            "confidence_distribution": self._get_confidence_distribution(),
            "review_required": [
                {
                    "question_id": d.question_id,
                    "reason": d.warnings[0] if d.warnings else "Low confidence"
                }
                for d in self.decisions.values() if d.requires_review
            ]
        }
        
    def _get_confidence_distribution(self) -> Dict[str, int]:
        """Get distribution of confidence scores."""
        bins = {"0-20": 0, "20-40": 0, "40-60": 0, "60-80": 0, "80-100": 0}
        
        for decision in self.decisions.values():
            conf = decision.confidence * 100  # Convert to percentage
            if conf <= 20:
                bins["0-20"] += 1
            elif conf <= 40:
                bins["20-40"] += 1
            elif conf <= 60:
                bins["40-60"] += 1
            elif conf <= 80:
                bins["60-80"] += 1
            else:
                bins["80-100"] += 1
                
        return bins
    
    def export_to_yaml_metadata(self) -> Dict[str, Any]:
        """Export decision tracking for YAML output."""
        return {
            "decision_attribution": {
                qid: {
                    "method": d.method.value if d.method else "unknown",
                    "confidence": f"{d.confidence * 100:.1f}%",
                    "llm_used": d.llm_used,
                    "rationale": d.rationale,
                    "requires_review": d.requires_review,
                    "warnings": d.warnings
                }
                for qid, d in self.decisions.items()
            },
            "summary": self.get_summary_report()
        }


# Global decision tracker instance
decision_tracker = None


def initialize_decision_tracker() -> DecisionTracker:
    """Initialize the global decision tracker."""
    global decision_tracker
    decision_tracker = DecisionTracker()
    return decision_tracker


def get_decision_tracker() -> Optional[DecisionTracker]:
    """Get the global decision tracker instance."""
    return decision_tracker


def track_decision(attribution: DecisionAttribution):
    """Track a decision using the global tracker."""
    if decision_tracker:
        decision_tracker.track_decision(attribution)