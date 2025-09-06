"""
Red flag detection system for contract analysis.
Identifies critical legal and business issues that require immediate attention.
"""

import re
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from enum import Enum


class RedFlagSeverity(Enum):
    CRITICAL = "Critical"
    HIGH = "High"
    MEDIUM = "Medium"


@dataclass
class RedFlag:
    """Represents a detected red flag in contract text."""
    flag_id: str
    severity: RedFlagSeverity
    category: str
    title: str
    description: str
    detected_text: str
    location: Optional[str] = None
    immediate_action: str = ""
    business_impact: str = ""


class RedFlagDetector:
    """
    Detects critical legal and business red flags in contract text.
    """
    
    def __init__(self):
        self.red_flag_patterns = self._initialize_red_flag_patterns()
        self.severity_weights = {
            RedFlagSeverity.CRITICAL: 100,
            RedFlagSeverity.HIGH: 75,
            RedFlagSeverity.MEDIUM: 50
        }
    
    def _initialize_red_flag_patterns(self) -> Dict[str, List[Dict[str, Any]]]:
        """Initialize comprehensive red flag detection patterns."""
        return {
            "liability_unlimited": [
                {
                    "pattern": r"(?i)(?:unlimited|no\s+limit|without\s+limitation).*liability",
                    "severity": RedFlagSeverity.CRITICAL,
                    "title": "Unlimited Liability Exposure",
                    "description": "Contract contains unlimited liability provisions",
                    "immediate_action": "REJECT or negotiate strict liability caps",
                    "business_impact": "Unlimited financial exposure for any breach"
                },
                {
                    "pattern": r"(?i)liable.*(?:all|any|every).*(?:loss|damage|claim|cost)",
                    "severity": RedFlagSeverity.HIGH,
                    "title": "Broad Liability Coverage",
                    "description": "Overly broad liability for all losses and damages",
                    "immediate_action": "Negotiate specific exclusions and limitations",
                    "business_impact": "Potential liability for unrelated third-party claims"
                }
            ],
            
            "indemnification_asymmetric": [
                {
                    "pattern": r"(?i)(?:you|customer|client).*(?:shall|will|agree).*indemnify.*(?:us|company|provider)(?!.*we.*indemnify)",
                    "severity": RedFlagSeverity.HIGH,
                    "title": "One-Sided Indemnification",
                    "description": "Asymmetric indemnification favoring counterparty",
                    "immediate_action": "Demand mutual indemnification provisions",
                    "business_impact": "One-way protection only benefits counterparty"
                },
                {
                    "pattern": r"(?i)indemnify.*(?:attorneys['\s]fees|legal\s+costs|defense\s+costs)",
                    "severity": RedFlagSeverity.MEDIUM,
                    "title": "Legal Fee Indemnification",
                    "description": "Required to pay counterparty's legal fees",
                    "immediate_action": "Negotiate mutual attorney fee provisions",
                    "business_impact": "Potential for significant legal cost exposure"
                }
            ],
            
            "ip_overreach": [
                {
                    "pattern": r"(?i)(?:assign|transfer|grant).*(?:all|entire|complete).*intellectual\s+property",
                    "severity": RedFlagSeverity.CRITICAL,
                    "title": "Broad IP Assignment",
                    "description": "Assignment of all intellectual property rights",
                    "immediate_action": "Limit to specific work product only",
                    "business_impact": "Loss of all IP including pre-existing and unrelated IP"
                },
                {
                    "pattern": r"(?i)work.*(?:made\s+for\s+hire|for\s+hire)",
                    "severity": RedFlagSeverity.HIGH,
                    "title": "Work for Hire Designation",
                    "description": "All work designated as work for hire",
                    "immediate_action": "Clarify scope of work for hire provisions",
                    "business_impact": "Automatic IP ownership transfer to counterparty"
                }
            ],
            
            "termination_unfair": [
                {
                    "pattern": r"(?i)(?:we|company|provider).*(?:may|can|right).*terminat.*(?:immediately|any\s+time|without\s+notice)",
                    "severity": RedFlagSeverity.HIGH,
                    "title": "Unilateral Termination Rights",
                    "description": "Counterparty has broad termination rights",
                    "immediate_action": "Negotiate mutual termination rights with notice",
                    "business_impact": "Business disruption risk from sudden termination"
                },
                {
                    "pattern": r"(?i)terminat.*(?:without\s+cause|for\s+convenience).*(?:immediately|no\s+notice)",
                    "severity": RedFlagSeverity.MEDIUM,
                    "title": "Immediate Termination for Convenience",
                    "description": "Contract can be terminated immediately without cause",
                    "immediate_action": "Require minimum notice period",
                    "business_impact": "No protection against arbitrary termination"
                }
            ],
            
            "payment_unfavorable": [
                {
                    "pattern": r"(?i)(?:all\s+amounts|entire\s+balance|full\s+payment).*(?:immediately\s+due|payable\s+immediately)",
                    "severity": RedFlagSeverity.HIGH,
                    "title": "Payment Acceleration",
                    "description": "All payments become immediately due upon default",
                    "immediate_action": "Limit acceleration to material uncured defaults",
                    "business_impact": "Immediate cash flow impact upon any breach"
                },
                {
                    "pattern": r"(?i)(?:late\s+fee|interest).*(?:[2-9]\d|[1-9]\d\d+)%",
                    "severity": RedFlagSeverity.MEDIUM,
                    "title": "Excessive Late Fees",
                    "description": "Unreasonably high late payment penalties",
                    "immediate_action": "Negotiate reasonable late fee rates (typically 1.5% monthly)",
                    "business_impact": "Punitive charges for payment delays"
                }
            ],
            
            "confidentiality_overreach": [
                {
                    "pattern": r"(?i)confidential.*(?:perpetual|indefinite|forever|permanent)",
                    "severity": RedFlagSeverity.HIGH,
                    "title": "Perpetual Confidentiality",
                    "description": "Confidentiality obligations last forever",
                    "immediate_action": "Negotiate time limit (typically 3-5 years)",
                    "business_impact": "Permanent business restrictions and compliance burden"
                },
                {
                    "pattern": r"(?i)confidential.*(?:all\s+information|any\s+information|everything\s+disclosed)",
                    "severity": RedFlagSeverity.MEDIUM,
                    "title": "Overly Broad Confidentiality",
                    "description": "All shared information deemed confidential",
                    "immediate_action": "Define confidential information specifically",
                    "business_impact": "Difficulty using general industry knowledge"
                }
            ],
            
            "governing_law_hostile": [
                {
                    "pattern": r"(?i)governed.*(?:laws?\s+of\s+(?:north\s+korea|iran|cuba|syria))",
                    "severity": RedFlagSeverity.CRITICAL,
                    "title": "Hostile Jurisdiction",
                    "description": "Contract governed by hostile or sanctioned jurisdiction",
                    "immediate_action": "REJECT - Legal/compliance violation risk",
                    "business_impact": "Potential violation of sanctions and trade restrictions"
                },
                {
                    "pattern": r"(?i)exclusive\s+jurisdiction.*(?:foreign|international|offshore)",
                    "severity": RedFlagSeverity.HIGH,
                    "title": "Exclusive Foreign Jurisdiction",
                    "description": "Must litigate exclusively in foreign jurisdiction",
                    "immediate_action": "Negotiate for home jurisdiction or arbitration",
                    "business_impact": "Expensive and complex foreign litigation"
                }
            ],
            
            "compliance_violations": [
                {
                    "pattern": r"(?i)(?:anti-?bribery|fcpa|corruption).*(?:not\s+applicable|excluded|waived)",
                    "severity": RedFlagSeverity.CRITICAL,
                    "title": "Anti-Corruption Waiver",
                    "description": "Anti-bribery/FCPA compliance waived or excluded",
                    "immediate_action": "REJECT - Compliance violation risk",
                    "business_impact": "Potential criminal liability and regulatory violations"
                },
                {
                    "pattern": r"(?i)(?:export|trade).*(?:restriction|compliance).*(?:not\s+applicable|waived)",
                    "severity": RedFlagSeverity.HIGH,
                    "title": "Export Control Waiver",
                    "description": "Export control compliance requirements waived",
                    "immediate_action": "Restore full export control compliance",
                    "business_impact": "Potential violations of international trade laws"
                }
            ],
            
            "data_privacy_violations": [
                {
                    "pattern": r"(?i)(?:gdpr|privacy|data\s+protection).*(?:not\s+applicable|excluded|waived)",
                    "severity": RedFlagSeverity.HIGH,
                    "title": "Privacy Law Exclusion",
                    "description": "Data privacy law compliance excluded",
                    "immediate_action": "Restore full privacy law compliance",
                    "business_impact": "Regulatory fines and privacy violations"
                },
                {
                    "pattern": r"(?i)data.*(?:sold|shared|disclosed).*(?:third\s+part|affiliate|subsidiary)",
                    "severity": RedFlagSeverity.MEDIUM,
                    "title": "Broad Data Sharing",
                    "description": "Customer data may be shared with third parties",
                    "immediate_action": "Limit data sharing and require consent",
                    "business_impact": "Privacy breaches and regulatory compliance issues"
                }
            ]
        }
    
    def detect_red_flags(self, text: str, location_info: Optional[Dict[str, Any]] = None) -> List[RedFlag]:
        """
        Detect all red flags in the given text.
        """
        detected_flags = []
        flag_counter = 1
        
        for category, patterns in self.red_flag_patterns.items():
            for pattern_info in patterns:
                pattern = pattern_info["pattern"]
                matches = re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE)
                
                for match in matches:
                    # Extract the matched text with some context
                    start = max(0, match.start() - 50)
                    end = min(len(text), match.end() + 50)
                    context_text = text[start:end].strip()
                    
                    # Create location string
                    location = "Unknown location"
                    if location_info:
                        location_parts = []
                        if location_info.get("section_name"):
                            location_parts.append(f"Section: {location_info['section_name']}")
                        if location_info.get("page_number"):
                            location_parts.append(f"Page: {location_info['page_number']}")
                        if location_parts:
                            location = ", ".join(location_parts)
                    
                    red_flag = RedFlag(
                        flag_id=f"RF_{flag_counter:03d}",
                        severity=pattern_info["severity"],
                        category=category,
                        title=pattern_info["title"],
                        description=pattern_info["description"],
                        detected_text=context_text,
                        location=location,
                        immediate_action=pattern_info["immediate_action"],
                        business_impact=pattern_info["business_impact"]
                    )
                    
                    detected_flags.append(red_flag)
                    flag_counter += 1
        
        return detected_flags
    
    def analyze_document_red_flags(self, classified_sentences: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Analyze the entire document for red flags and provide comprehensive assessment.
        """
        all_red_flags = []
        severity_counts = {severity.value: 0 for severity in RedFlagSeverity}
        category_counts = {}
        
        for sentence_data in classified_sentences:
            sentence = sentence_data.get("sentence", "")
            location_info = {
                "section_name": sentence_data.get("section_name"),
                "page_number": sentence_data.get("page_number"),
                "sentence_id": sentence_data.get("sentence_id")
            }
            
            flags = self.detect_red_flags(sentence, location_info)
            all_red_flags.extend(flags)
            
            # Update counts
            for flag in flags:
                severity_counts[flag.severity.value] += 1
                category_counts[flag.category] = category_counts.get(flag.category, 0) + 1
        
        # Calculate overall risk assessment
        critical_flags = severity_counts["Critical"]
        high_flags = severity_counts["High"]
        medium_flags = severity_counts["Medium"]
        
        # Determine overall recommendation
        if critical_flags > 0:
            overall_recommendation = "DO NOT SIGN - Critical issues require resolution"
            risk_level = "CRITICAL"
        elif high_flags >= 3:
            overall_recommendation = "CAUTION - Multiple high-risk issues require negotiation"
            risk_level = "HIGH"
        elif high_flags >= 1:
            overall_recommendation = "REVIEW REQUIRED - Address high-risk provisions"
            risk_level = "HIGH"
        elif medium_flags >= 3:
            overall_recommendation = "NEGOTIATE - Address medium-risk provisions"
            risk_level = "MEDIUM"
        else:
            overall_recommendation = "ACCEPTABLE - Standard contract review recommended"
            risk_level = "LOW"
        
        # Priority red flags (critical and high severity)
        priority_flags = [flag for flag in all_red_flags 
                         if flag.severity in [RedFlagSeverity.CRITICAL, RedFlagSeverity.HIGH]]
        
        # Generate action items
        action_items = self._generate_action_items(all_red_flags)
        
        return {
            "total_red_flags": len(all_red_flags),
            "severity_breakdown": severity_counts,
            "category_breakdown": category_counts,
            "overall_risk_level": risk_level,
            "overall_recommendation": overall_recommendation,
            "priority_flags": [self._serialize_red_flag(flag) for flag in priority_flags],
            "all_red_flags": [self._serialize_red_flag(flag) for flag in all_red_flags],
            "action_items": action_items,
            "business_impact_summary": self._generate_business_impact_summary(all_red_flags),
            "negotiation_priorities": self._generate_negotiation_priorities(all_red_flags)
        }
    
    def _serialize_red_flag(self, flag: RedFlag) -> Dict[str, Any]:
        """Convert RedFlag object to dictionary for JSON serialization."""
        return {
            "flag_id": flag.flag_id,
            "severity": flag.severity.value,
            "category": flag.category,
            "title": flag.title,
            "description": flag.description,
            "detected_text": flag.detected_text,
            "location": flag.location,
            "immediate_action": flag.immediate_action,
            "business_impact": flag.business_impact
        }
    
    def _generate_action_items(self, red_flags: List[RedFlag]) -> List[Dict[str, Any]]:
        """Generate prioritized action items based on detected red flags."""
        action_items = []
        
        # Group by severity and category
        critical_actions = set()
        high_actions = set()
        medium_actions = set()
        
        for flag in red_flags:
            action = flag.immediate_action
            if flag.severity == RedFlagSeverity.CRITICAL:
                critical_actions.add(action)
            elif flag.severity == RedFlagSeverity.HIGH:
                high_actions.add(action)
            else:
                medium_actions.add(action)
        
        # Build prioritized action list
        priority = 1
        for action in critical_actions:
            action_items.append({
                "priority": priority,
                "severity": "Critical",
                "action": action,
                "timeline": "Immediate"
            })
            priority += 1
        
        for action in high_actions:
            action_items.append({
                "priority": priority,
                "severity": "High",
                "action": action,
                "timeline": "Before signing"
            })
            priority += 1
        
        for action in medium_actions:
            action_items.append({
                "priority": priority,
                "severity": "Medium",
                "action": action,
                "timeline": "During negotiation"
            })
            priority += 1
        
        return action_items[:10]  # Top 10 priority actions
    
    def _generate_business_impact_summary(self, red_flags: List[RedFlag]) -> Dict[str, Any]:
        """Generate a summary of business impacts from red flags."""
        impacts = {
            "financial_risk": [],
            "operational_risk": [],
            "legal_risk": [],
            "compliance_risk": []
        }
        
        for flag in red_flags:
            impact = flag.business_impact.lower()
            
            if any(term in impact for term in ["financial", "liability", "cost", "payment", "fee"]):
                impacts["financial_risk"].append(flag.title)
            elif any(term in impact for term in ["operational", "business", "termination", "disruption"]):
                impacts["operational_risk"].append(flag.title)
            elif any(term in impact for term in ["compliance", "regulatory", "violation", "sanctions"]):
                impacts["compliance_risk"].append(flag.title)
            else:
                impacts["legal_risk"].append(flag.title)
        
        return {
            "financial_exposure": len(impacts["financial_risk"]),
            "operational_risks": len(impacts["operational_risk"]),
            "legal_risks": len(impacts["legal_risk"]),
            "compliance_risks": len(impacts["compliance_risk"]),
            "detailed_risks": impacts
        }
    
    def _generate_negotiation_priorities(self, red_flags: List[RedFlag]) -> List[str]:
        """Generate prioritized list of negotiation points."""
        priorities = []
        
        # Critical issues first
        critical_flags = [f for f in red_flags if f.severity == RedFlagSeverity.CRITICAL]
        if critical_flags:
            priorities.append("1. CRITICAL: Address unlimited liability and IP overreach")
        
        # High-priority categories
        categories_present = set(f.category for f in red_flags if f.severity == RedFlagSeverity.HIGH)
        
        if "liability_unlimited" in categories_present:
            priorities.append("2. Negotiate liability caps and limitations")
        
        if "indemnification_asymmetric" in categories_present:
            priorities.append("3. Establish mutual indemnification provisions")
        
        if "termination_unfair" in categories_present:
            priorities.append("4. Balance termination rights and notice periods")
        
        if "ip_overreach" in categories_present:
            priorities.append("5. Limit IP assignment to specific deliverables")
        
        return priorities[:8]  # Top 8 negotiation priorities


# Global instance for easy import
red_flag_detector = RedFlagDetector()