"""
Quality analysis utility for comprehensive document processing assessment.
Integrates with confidence scoring to provide overall document quality ratings.
"""

from typing import Dict, List, Any
from datetime import datetime
from utils.confidence_scorer import confidence_scorer


class QualityAnalyzer:
    """
    Comprehensive quality analysis for document processing workflow.
    Provides overall confidence ratings and quality assessments.
    """
    
    def __init__(self):
        self.confidence_thresholds = {
            "excellent": 90,
            "good": 75,
            "acceptable": 60,
            "needs_review": 40,
            "poor": 0
        }
        
        self.quality_weights = {
            "classification_quality": 0.3,
            "extraction_quality": 0.35,
            "processing_reliability": 0.2,
            "completeness": 0.15
        }
    
    def analyze_classification_quality(self, classified_sentences: List[Dict[str, Any]], 
                                     classification_metrics: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze quality of sentence classification results.
        """
        if not classified_sentences:
            return {
                "classification_quality_score": 0,
                "confidence_distribution": {},
                "issues": ["No classified sentences available"],
                "recommendations": ["Investigate classification failure"]
            }
        
        # Extract confidence scores
        confidence_scores = []
        review_needed = 0
        errors = 0
        
        for sentence_data in classified_sentences:
            confidence = sentence_data.get("confidence", 0)
            if confidence > 0:
                confidence_scores.append(confidence)
            
            if sentence_data.get("needs_manual_review", False):
                review_needed += 1
            
            if sentence_data.get("error"):
                errors += 1
        
        # Calculate quality metrics
        avg_confidence = sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0
        min_confidence = min(confidence_scores) if confidence_scores else 0
        max_confidence = max(confidence_scores) if confidence_scores else 0
        
        # Confidence distribution
        distribution = {
            "excellent": sum(1 for c in confidence_scores if c >= 90),
            "good": sum(1 for c in confidence_scores if 75 <= c < 90),
            "acceptable": sum(1 for c in confidence_scores if 60 <= c < 75),
            "needs_review": sum(1 for c in confidence_scores if 40 <= c < 60),
            "poor": sum(1 for c in confidence_scores if c < 40)
        }
        
        # Calculate quality penalty
        total_sentences = len(classified_sentences)
        error_rate = errors / total_sentences if total_sentences > 0 else 0
        review_rate = review_needed / total_sentences if total_sentences > 0 else 0
        
        quality_penalty = (error_rate * 30) + (review_rate * 15)
        classification_quality_score = max(0, avg_confidence - quality_penalty)
        
        # Generate issues and recommendations
        issues = []
        recommendations = []
        
        if error_rate > 0.1:
            issues.append(f"High error rate: {error_rate:.1%}")
            recommendations.append("Review classification pipeline for errors")
        
        if review_rate > 0.3:
            issues.append(f"High manual review rate: {review_rate:.1%}")
            recommendations.append("Consider adjusting confidence thresholds")
        
        if avg_confidence < 60:
            issues.append(f"Low average confidence: {avg_confidence:.1f}")
            recommendations.append("Improve training data or prompt engineering")
        
        return {
            "classification_quality_score": classification_quality_score,
            "average_confidence": avg_confidence,
            "confidence_range": {"min": min_confidence, "max": max_confidence},
            "confidence_distribution": distribution,
            "error_rate": error_rate,
            "review_rate": review_rate,
            "issues": issues,
            "recommendations": recommendations
        }
    
    def analyze_extraction_quality(self, questionnaire_responses: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze quality of question-answer extraction results.
        """
        if not questionnaire_responses:
            return {
                "extraction_quality_score": 0,
                "completeness_rate": 0,
                "issues": ["No questionnaire responses available"],
                "recommendations": ["Investigate extraction failure"]
            }
        
        total_questions = 0
        answered_questions = 0
        confidence_scores = []
        
        for section_key, section_data in questionnaire_responses.items():
            if isinstance(section_data, dict) and "questions" in section_data:
                for question in section_data["questions"]:
                    total_questions += 1
                    
                    answer = question.get("answer", "")
                    if answer and answer.strip() and answer != "DETERMINISTIC_FIELD":
                        answered_questions += 1
                        
                        # Use confidence scorer for extraction quality
                        if "confidence" not in question:
                            confidence_result = confidence_scorer.score_extraction_confidence(
                                question.get("prompt", ""),
                                answer,
                                ""  # Would need source text for better scoring
                            )
                            confidence_scores.append(confidence_result.get("overall_confidence", 50))
                        else:
                            confidence_scores.append(question["confidence"])
        
        # Calculate metrics
        completeness_rate = answered_questions / total_questions if total_questions > 0 else 0
        avg_confidence = sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0
        
        # Quality score combines completeness and confidence
        extraction_quality_score = (completeness_rate * 50) + (avg_confidence * 0.5)
        
        # Generate issues and recommendations
        issues = []
        recommendations = []
        
        if completeness_rate < 0.8:
            issues.append(f"Low completeness rate: {completeness_rate:.1%}")
            recommendations.append("Review extraction logic for missing answers")
        
        if avg_confidence < 60:
            issues.append(f"Low extraction confidence: {avg_confidence:.1f}")
            recommendations.append("Improve question-answer matching")
        
        return {
            "extraction_quality_score": extraction_quality_score,
            "completeness_rate": completeness_rate,
            "average_confidence": avg_confidence,
            "total_questions": total_questions,
            "answered_questions": answered_questions,
            "issues": issues,
            "recommendations": recommendations
        }
    
    def analyze_processing_reliability(self, processing_errors: List[Dict[str, Any]], 
                                     processing_metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze reliability of the processing pipeline.
        """
        # Count errors by severity
        error_counts = {"critical": 0, "recoverable": 0, "warning": 0, "info": 0}
        
        for error in processing_errors:
            severity = error.get("severity", "warning")
            error_counts[severity] = error_counts.get(severity, 0) + 1
        
        # Calculate reliability penalty
        total_errors = sum(error_counts.values())
        reliability_penalty = (error_counts["critical"] * 40) + (error_counts["recoverable"] * 20) + (error_counts["warning"] * 5)
        
        # Base reliability score
        base_reliability = 100 - min(reliability_penalty, 100)
        
        # Check for fallback usage
        fallback_penalty = 0
        if processing_metadata.get("fallback_strategies_used"):
            fallback_penalty = len(processing_metadata["fallback_strategies_used"]) * 10
        
        processing_reliability_score = max(0, base_reliability - fallback_penalty)
        
        # Generate issues and recommendations
        issues = []
        recommendations = []
        
        if error_counts["critical"] > 0:
            issues.append(f"Critical errors: {error_counts['critical']}")
            recommendations.append("Address critical failures immediately")
        
        if total_errors > 10:
            issues.append(f"High error count: {total_errors}")
            recommendations.append("Review processing pipeline stability")
        
        if fallback_penalty > 20:
            issues.append("Multiple fallback strategies used")
            recommendations.append("Investigate primary processing failures")
        
        return {
            "processing_reliability_score": processing_reliability_score,
            "error_counts": error_counts,
            "total_errors": total_errors,
            "fallback_penalty": fallback_penalty,
            "issues": issues,
            "recommendations": recommendations
        }
    
    def calculate_overall_quality_rating(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculate comprehensive quality rating for the entire document analysis.
        """
        print("--- CALCULATING OVERALL QUALITY RATING ---")
        
        # Analyze individual components
        classification_analysis = self.analyze_classification_quality(
            state.get("classified_sentences", []),
            state.get("classification_metrics", {})
        )
        
        extraction_analysis = self.analyze_extraction_quality(
            state.get("questionnaire_responses", {})
        )
        
        processing_analysis = self.analyze_processing_reliability(
            state.get("processing_errors", []),
            state.get("processing_metadata", {})
        )
        
        # Calculate completeness
        total_expected_outputs = 4  # classified sentences, questionnaire responses, extracted data, final output
        actual_outputs = 0
        
        if state.get("classified_sentences"):
            actual_outputs += 1
        if state.get("questionnaire_responses"):
            actual_outputs += 1
        if state.get("extracted_data"):
            actual_outputs += 1
        if state.get("final_spreadsheet_row"):
            actual_outputs += 1
        
        completeness_score = (actual_outputs / total_expected_outputs) * 100
        
        # Calculate weighted overall score
        overall_score = (
            classification_analysis["classification_quality_score"] * self.quality_weights["classification_quality"] +
            extraction_analysis["extraction_quality_score"] * self.quality_weights["extraction_quality"] +
            processing_analysis["processing_reliability_score"] * self.quality_weights["processing_reliability"] +
            completeness_score * self.quality_weights["completeness"]
        )
        
        # Determine quality grade
        if overall_score >= self.confidence_thresholds["excellent"]:
            quality_grade = "A"
            quality_level = "Excellent"
        elif overall_score >= self.confidence_thresholds["good"]:
            quality_grade = "B"
            quality_level = "Good"
        elif overall_score >= self.confidence_thresholds["acceptable"]:
            quality_grade = "C"
            quality_level = "Acceptable"
        elif overall_score >= self.confidence_thresholds["needs_review"]:
            quality_grade = "D"
            quality_level = "Needs Review"
        else:
            quality_grade = "F"
            quality_level = "Poor"
        
        # Aggregate all issues and recommendations
        all_issues = (
            classification_analysis.get("issues", []) +
            extraction_analysis.get("issues", []) +
            processing_analysis.get("issues", [])
        )
        
        all_recommendations = (
            classification_analysis.get("recommendations", []) +
            extraction_analysis.get("recommendations", []) +
            processing_analysis.get("recommendations", [])
        )
        
        # Determine if manual review is required
        manual_review_required = (
            overall_score < self.confidence_thresholds["acceptable"] or
            len(all_issues) > 5 or
            any("critical" in issue.lower() for issue in all_issues)
        )
        
        quality_report = {
            "overall_quality_score": round(overall_score, 1),
            "quality_grade": quality_grade,
            "quality_level": quality_level,
            "manual_review_required": manual_review_required,
            "completeness_score": round(completeness_score, 1),
            "component_scores": {
                "classification": round(classification_analysis["classification_quality_score"], 1),
                "extraction": round(extraction_analysis["extraction_quality_score"], 1),
                "processing": round(processing_analysis["processing_reliability_score"], 1),
                "completeness": round(completeness_score, 1)
            },
            "detailed_analysis": {
                "classification": classification_analysis,
                "extraction": extraction_analysis,
                "processing": processing_analysis
            },
            "summary": {
                "total_issues": len(all_issues),
                "critical_issues": len([i for i in all_issues if "critical" in i.lower()]),
                "issues": all_issues[:10],  # Top 10 issues
                "recommendations": all_recommendations[:10]  # Top 10 recommendations
            },
            "generated_at": datetime.now().isoformat()
        }
        
        print(f"Overall Quality Score: {overall_score:.1f} ({quality_grade})")
        print(f"Manual Review Required: {manual_review_required}")
        print(f"Total Issues: {len(all_issues)}")
        
        return quality_report


# Global instance for easy import
quality_analyzer = QualityAnalyzer()