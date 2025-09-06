"""
Risk assessment utility for contract clause analysis.
Provides risk scoring, red flag detection, and business impact assessment.
"""

import re
from typing import Dict, List, Any, Optional
from enum import Enum
from dataclasses import dataclass
from utils.confidence_scorer import confidence_scorer


class RiskLevel(Enum):
    CRITICAL = "Critical"
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


class BusinessImpact(Enum):
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


@dataclass
class RiskIndicator:
    """Represents a specific risk indicator in contract text."""
    indicator_type: str
    pattern: str
    risk_level: RiskLevel
    description: str
    mitigation_guidance: str


class RiskAssessor:
    """
    Comprehensive risk assessment for contract clauses and terms.
    """
    
    def __init__(self):
        self.risk_indicators = self._initialize_risk_indicators()
        self.risk_weights = {
            RiskLevel.CRITICAL: 100,
            RiskLevel.HIGH: 75,
            RiskLevel.MEDIUM: 50,
            RiskLevel.LOW: 25
        }
        
        # Business impact factors
        self.impact_factors = {
            "unlimited_liability": BusinessImpact.HIGH,
            "broad_indemnification": BusinessImpact.HIGH,
            "ip_assignment": BusinessImpact.HIGH,
            "termination_rights": BusinessImpact.MEDIUM,
            "confidentiality_broad": BusinessImpact.MEDIUM,
            "governing_law_unfavorable": BusinessImpact.MEDIUM,
            "payment_terms_unfavorable": BusinessImpact.MEDIUM,
            "warranty_broad": BusinessImpact.MEDIUM,
            "limitation_exclusions": BusinessImpact.LOW,
            "notice_requirements": BusinessImpact.LOW
        }
    
    def _initialize_risk_indicators(self) -> Dict[str, List[RiskIndicator]]:
        """Initialize comprehensive risk indicator patterns."""
        return {
            "liability": [
                RiskIndicator(
                    "unlimited_liability",
                    r"(?i)(?:unlimited|no\s+limitation|without\s+limit).*liability",
                    RiskLevel.CRITICAL,
                    "Unlimited liability exposure",
                    "Negotiate cap on liability or specific exclusions"
                ),
                RiskIndicator(
                    "broad_liability",
                    r"(?i)liable\s+for.*(?:indirect|consequential|punitive|special).*damages",
                    RiskLevel.HIGH,
                    "Broad liability for consequential damages",
                    "Exclude consequential and indirect damages"
                ),
                RiskIndicator(
                    "liability_exclusions",
                    r"(?i)limitation.*liability.*shall\s+not\s+apply",
                    RiskLevel.HIGH,
                    "Liability limitation exclusions",
                    "Review exclusion scope and negotiate limitations"
                )
            ],
            
            "indemnification": [
                RiskIndicator(
                    "broad_indemnification",
                    r"(?i)indemnify.*(?:against\s+all|for\s+any\s+and\s+all|from\s+and\s+against\s+any)",
                    RiskLevel.HIGH,
                    "Broad indemnification obligations",
                    "Limit indemnification scope to specific claims"
                ),
                RiskIndicator(
                    "mutual_indemnification",
                    r"(?i)(?:mutual|each\s+party).*indemnif",
                    RiskLevel.MEDIUM,
                    "Mutual indemnification clause",
                    "Ensure balanced indemnification obligations"
                )
            ],
            
            "intellectual_property": [
                RiskIndicator(
                    "ip_assignment_broad",
                    r"(?i)(?:assign|transfer).*(?:all|any).*intellectual\s+property",
                    RiskLevel.CRITICAL,
                    "Broad IP assignment requirement",
                    "Limit IP assignment to work specifically created"
                ),
                RiskIndicator(
                    "ip_infringement_warranty",
                    r"(?i)warrant.*(?:does\s+not\s+infringe|non-infringement)",
                    RiskLevel.HIGH,
                    "IP infringement warranty",
                    "Qualify warranty with knowledge limitations"
                )
            ],
            
            "termination": [
                RiskIndicator(
                    "termination_convenience",
                    r"(?i)terminat.*(?:at\s+any\s+time|for\s+convenience|without\s+cause)",
                    RiskLevel.MEDIUM,
                    "Termination for convenience",
                    "Ensure mutual termination rights or notice period"
                ),
                RiskIndicator(
                    "termination_immediate",
                    r"(?i)(?:immediate|immediately).*terminat",
                    RiskLevel.HIGH,
                    "Immediate termination rights",
                    "Add cure period for non-material breaches"
                )
            ],
            
            "confidentiality": [
                RiskIndicator(
                    "confidentiality_broad",
                    r"(?i)confidential.*(?:all\s+information|any\s+information|everything)",
                    RiskLevel.MEDIUM,
                    "Overly broad confidentiality definition",
                    "Define confidential information more specifically"
                ),
                RiskIndicator(
                    "confidentiality_perpetual",
                    r"(?i)confidential.*(?:perpetual|indefinite|forever)",
                    RiskLevel.HIGH,
                    "Perpetual confidentiality obligations",
                    "Negotiate time limit on confidentiality"
                )
            ],
            
            "governing_law": [
                RiskIndicator(
                    "foreign_jurisdiction",
                    r"(?i)governed\s+by.*(?:laws\s+of.*(?:england|delaware|new\s+york|california))",
                    RiskLevel.LOW,
                    "Foreign jurisdiction governing law",
                    "Consider implications of foreign law"
                ),
                RiskIndicator(
                    "exclusive_jurisdiction",
                    r"(?i)exclusive\s+jurisdiction",
                    RiskLevel.MEDIUM,
                    "Exclusive jurisdiction clause",
                    "Negotiate for non-exclusive jurisdiction"
                )
            ],
            
            "payment": [
                RiskIndicator(
                    "payment_acceleration",
                    r"(?i)(?:all\s+amounts|entire\s+amount).*(?:immediately\s+due|become\s+due)",
                    RiskLevel.HIGH,
                    "Payment acceleration clause",
                    "Limit acceleration to material defaults"
                ),
                RiskIndicator(
                    "late_fees_high",
                    r"(?i)(?:late\s+fee|interest).*(?:[2-9]\d|1[5-9])%",
                    RiskLevel.MEDIUM,
                    "High late payment fees",
                    "Negotiate reasonable late fee rates"
                )
            ],
            
            "warranty": [
                RiskIndicator(
                    "warranty_broad",
                    r"(?i)warrant.*(?:all|complete|total|absolute)",
                    RiskLevel.MEDIUM,
                    "Broad warranty language",
                    "Qualify warranties with materiality thresholds"
                ),
                RiskIndicator(
                    "warranty_performance",
                    r"(?i)warrant.*(?:performance|results|outcomes)",
                    RiskLevel.HIGH,
                    "Performance warranty",
                    "Limit to effort-based rather than results-based"
                )
            ]
        }
    
    def assess_clause_risk(self, clause_text: str, clause_type: Optional[str] = None) -> Dict[str, Any]:
        """
        Assess risk level of a specific contract clause.
        """
        if not clause_text.strip():
            return {
                "risk_level": RiskLevel.LOW.value,
                "risk_score": 0,
                "confidence": 0,
                "indicators": [],
                "business_impact": BusinessImpact.LOW.value,
                "mitigation_urgency": "Low"
            }
        
        detected_indicators = []
        risk_scores = []
        
        # Check each category of risk indicators
        for category, indicators in self.risk_indicators.items():
            for indicator in indicators:
                if re.search(indicator.pattern, clause_text):
                    detected_indicators.append({
                        "type": indicator.indicator_type,
                        "category": category,
                        "risk_level": indicator.risk_level.value,
                        "description": indicator.description,
                        "mitigation_guidance": indicator.mitigation_guidance,
                        "pattern_matched": indicator.pattern
                    })
                    risk_scores.append(self.risk_weights[indicator.risk_level])
        
        # Calculate overall risk score
        if risk_scores:
            # Use highest risk score as primary, with additional indicators adding weight
            max_risk = max(risk_scores)
            additional_risk = sum(score * 0.1 for score in risk_scores[1:])  # 10% weight for additional risks
            total_risk_score = min(100, max_risk + additional_risk)
        else:
            total_risk_score = 0
        
        # Determine overall risk level
        if total_risk_score >= 90:
            overall_risk = RiskLevel.CRITICAL
        elif total_risk_score >= 70:
            overall_risk = RiskLevel.HIGH
        elif total_risk_score >= 40:
            overall_risk = RiskLevel.MEDIUM
        else:
            overall_risk = RiskLevel.LOW
        
        # Assess business impact
        business_impact = self._assess_business_impact(detected_indicators)
        
        # Determine mitigation urgency
        mitigation_urgency = self._determine_mitigation_urgency(overall_risk, business_impact)
        
        # Use Mixtral for additional risk assessment if available
        enhanced_assessment = self._get_enhanced_risk_assessment(clause_text, detected_indicators)
        
        return {
            "risk_level": overall_risk.value,
            "risk_score": round(total_risk_score, 1),
            "confidence": enhanced_assessment.get("confidence", 75),
            "indicators": detected_indicators,
            "business_impact": business_impact.value,
            "mitigation_urgency": mitigation_urgency,
            "enhanced_assessment": enhanced_assessment,
            "recommendations": self._generate_recommendations(detected_indicators),
            "clause_analysis": {
                "text_length": len(clause_text),
                "complexity_score": self._calculate_complexity_score(clause_text),
                "indicator_count": len(detected_indicators)
            }
        }
    
    def _assess_business_impact(self, indicators: List[Dict[str, Any]]) -> BusinessImpact:
        """Assess the business impact based on detected indicators."""
        if not indicators:
            return BusinessImpact.LOW
        
        impact_scores = []
        for indicator in indicators:
            indicator_type = indicator.get("type", "")
            if indicator_type in self.impact_factors:
                impact = self.impact_factors[indicator_type]
                if impact == BusinessImpact.HIGH:
                    impact_scores.append(3)
                elif impact == BusinessImpact.MEDIUM:
                    impact_scores.append(2)
                else:
                    impact_scores.append(1)
        
        if not impact_scores:
            return BusinessImpact.LOW
        
        avg_impact = sum(impact_scores) / len(impact_scores)
        if avg_impact >= 2.5:
            return BusinessImpact.HIGH
        elif avg_impact >= 1.5:
            return BusinessImpact.MEDIUM
        else:
            return BusinessImpact.LOW
    
    def _determine_mitigation_urgency(self, risk_level: RiskLevel, business_impact: BusinessImpact) -> str:
        """Determine the urgency of risk mitigation."""
        if risk_level == RiskLevel.CRITICAL or business_impact == BusinessImpact.HIGH:
            return "Immediate"
        elif risk_level == RiskLevel.HIGH:
            return "Soon"
        elif risk_level == RiskLevel.MEDIUM:
            return "Moderate"
        else:
            return "Low"
    
    def _calculate_complexity_score(self, text: str) -> float:
        """Calculate a complexity score for the clause text."""
        if not text:
            return 0.0
        
        # Factors contributing to complexity
        word_count = len(text.split())
        sentence_count = len(re.split(r'[.!?]+', text))
        avg_words_per_sentence = word_count / sentence_count if sentence_count > 0 else 0
        
        # Legal terminology indicators
        legal_terms = [r'whereas', r'notwithstanding', r'provided that', r'subject to', 
                      r'shall', r'pursuant to', r'heretofore', r'hereinafter']
        legal_term_count = sum(1 for term in legal_terms if re.search(term, text, re.IGNORECASE))
        
        # Complexity score (0-100)
        complexity = min(100, (
            (avg_words_per_sentence / 20) * 30 +  # Long sentences increase complexity
            (legal_term_count / len(legal_terms)) * 30 +  # Legal terminology
            (word_count / 200) * 40  # Overall length
        ))
        
        return round(complexity, 1)
    
    def _get_enhanced_risk_assessment(self, clause_text: str, indicators: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Get enhanced risk assessment using Mixtral if available."""
        try:
            risk_indicator_summary = [ind.get("description", "") for ind in indicators]
            
            enhanced_result = confidence_scorer.score_risk_assessment(
                clause_text, risk_indicator_summary
            )
            
            return enhanced_result
            
        except Exception as e:
            print(f"Enhanced risk assessment failed: {e}")
            return {
                "confidence": 75,
                "reasoning": "Pattern-based assessment only",
                "additional_insights": []
            }
    
    def _generate_recommendations(self, indicators: List[Dict[str, Any]]) -> List[str]:
        """Generate actionable recommendations based on detected indicators."""
        recommendations = []
        
        # Extract unique mitigation guidance
        guidance_seen = set()
        for indicator in indicators:
            guidance = indicator.get("mitigation_guidance", "")
            if guidance and guidance not in guidance_seen:
                recommendations.append(guidance)
                guidance_seen.add(guidance)
        
        # Add general recommendations based on risk patterns
        risk_categories = set(indicator.get("category", "") for indicator in indicators)
        
        if "liability" in risk_categories:
            recommendations.append("Consider adding mutual liability caps")
        
        if "indemnification" in risk_categories:
            recommendations.append("Ensure indemnification obligations are balanced")
        
        if len(indicators) > 3:
            recommendations.append("Request comprehensive legal review due to multiple risk factors")
        
        return recommendations[:10]  # Limit to top 10 recommendations
    
    def assess_document_risk_profile(self, classified_sentences: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Assess the overall risk profile of a contract document.
        """
        clause_assessments = []
        overall_indicators = []
        risk_scores = []
        
        for sentence_data in classified_sentences:
            sentence = sentence_data.get("sentence", "")
            classes = sentence_data.get("classes", [])
            
            # Focus on sentences with risk-relevant classifications
            risk_relevant_classes = [
                "Limitation of Liability", "Liability", "Indemnification", 
                "Intellectual Property", "Termination", "Confidentiality"
            ]
            
            if any(cls in risk_relevant_classes for cls in classes):
                clause_type = next((cls for cls in classes if cls in risk_relevant_classes), None)
                assessment = self.assess_clause_risk(sentence, clause_type)
                
                clause_assessments.append({
                    "sentence": sentence[:100] + "..." if len(sentence) > 100 else sentence,
                    "sentence_id": sentence_data.get("sentence_id"),
                    "classification": classes,
                    "assessment": assessment
                })
                
                overall_indicators.extend(assessment["indicators"])
                risk_scores.append(assessment["risk_score"])
        
        # Calculate overall risk metrics
        if risk_scores:
            avg_risk_score = sum(risk_scores) / len(risk_scores)
            max_risk_score = max(risk_scores)
            high_risk_clauses = sum(1 for score in risk_scores if score >= 70)
        else:
            avg_risk_score = 0
            max_risk_score = 0
            high_risk_clauses = 0
        
        # Determine overall document risk level
        if max_risk_score >= 90 or high_risk_clauses >= 3:
            document_risk_level = RiskLevel.CRITICAL
        elif max_risk_score >= 70 or high_risk_clauses >= 2:
            document_risk_level = RiskLevel.HIGH
        elif max_risk_score >= 40 or high_risk_clauses >= 1:
            document_risk_level = RiskLevel.MEDIUM
        else:
            document_risk_level = RiskLevel.LOW
        
        # Risk category summary
        risk_categories = {}
        for indicator in overall_indicators:
            category = indicator.get("category", "other")
            risk_categories[category] = risk_categories.get(category, 0) + 1
        
        return {
            "document_risk_level": document_risk_level.value,
            "average_risk_score": round(avg_risk_score, 1),
            "maximum_risk_score": round(max_risk_score, 1),
            "high_risk_clause_count": high_risk_clauses,
            "total_assessed_clauses": len(clause_assessments),
            "risk_categories": risk_categories,
            "clause_assessments": clause_assessments,
            "overall_indicators": overall_indicators,
            "document_recommendations": self._generate_document_recommendations(
                document_risk_level, risk_categories, high_risk_clauses
            )
        }
    
    def _generate_document_recommendations(self, risk_level: RiskLevel, 
                                         risk_categories: Dict[str, int], 
                                         high_risk_count: int) -> List[str]:
        """Generate document-level recommendations."""
        recommendations = []
        
        if risk_level == RiskLevel.CRITICAL:
            recommendations.append("URGENT: Immediate legal review required before signing")
            recommendations.append("Consider rejecting contract or requiring major revisions")
        elif risk_level == RiskLevel.HIGH:
            recommendations.append("Comprehensive legal review strongly recommended")
            recommendations.append("Negotiate key risk provisions before acceptance")
        elif risk_level == RiskLevel.MEDIUM:
            recommendations.append("Legal review recommended for risk provisions")
        
        # Category-specific recommendations
        if risk_categories.get("liability", 0) > 0:
            recommendations.append("Focus negotiation on liability and limitation clauses")
        
        if risk_categories.get("indemnification", 0) > 0:
            recommendations.append("Review indemnification scope and mutual obligations")
        
        if risk_categories.get("intellectual_property", 0) > 0:
            recommendations.append("Carefully review IP assignment and ownership provisions")
        
        if high_risk_count > 2:
            recommendations.append("Consider requesting alternative contract template")
        
        return recommendations


# Global instance for easy import
risk_assessor = RiskAssessor()