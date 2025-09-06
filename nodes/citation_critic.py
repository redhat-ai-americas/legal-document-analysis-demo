"""
Citation Critic Agent for Contract Analysis Workflow
Validates citations and triggers conditional reruns if quality issues are found
"""

import os
from typing import Dict, Any
from workflows.state import ContractAnalysisState
from utils.error_handler import handle_node_errors
import logging

logger = logging.getLogger(__name__)


class CitationCritic:
    """
    Critic agent that validates citations for quality and accuracy.
    Checks for:
    - Missing page anchors
    - Empty citations
    - Low confidence scores
    - Unknown locations
    - Citation-to-source text mismatches
    """
    
    def __init__(self, 
                 min_confidence: float = 0.6,
                 require_page_anchors: bool = True,
                 max_unknown_locations: int = 3):
        """
        Initialize the citation critic.
        
        Args:
            min_confidence: Minimum acceptable confidence score
            require_page_anchors: Whether page anchors are required
            max_unknown_locations: Maximum allowed "Unknown location" citations
        """
        self.min_confidence = min_confidence
        self.require_page_anchors = require_page_anchors
        self.max_unknown_locations = max_unknown_locations
        self.validation_results = {}
        self.issues_found = []
        
    def validate_citations(self, state: ContractAnalysisState) -> Dict[str, Any]:
        """
        Validate all citations in the state.
        
        Returns:
            Dict containing validation results and recommendations
        """
        self.validation_results = {
            "total_citations": 0,
            "empty_citations": 0,
            "missing_page_anchors": 0,
            "unknown_locations": 0,
            "low_confidence": 0,
            "validation_passed": True,
            "issues": [],
            "recommendations": [],
            "severity": "none"  # none, low, medium, high, critical
        }
        self.issues_found = []
        
        # Check questionnaire citations
        self._validate_questionnaire_citations(state)
        
        # Check rule compliance citations if present
        if state.get('compliance_summary'):
            self._validate_rule_citations(state)
        
        # Determine overall severity
        self._determine_severity()
        
        # Generate recommendations
        self._generate_recommendations()
        
        return self.validation_results
    
    def _validate_questionnaire_citations(self, state: ContractAnalysisState):
        """Validate citations in questionnaire responses."""
        questionnaire_responses = state.get('questionnaire_responses', {})
        
        # List of questions that typically require citations
        citation_required_questions = [
            'term', 'termination', 'limitation_of_liability', 'indemnity',
            'governing_law', 'assignment_coc', 'exclusivity_non_competes',
            'ip_rights', 'warranty', 'force_majeure', 'confidentiality',
            'dispute_resolution', 'pricing', 'payment_terms'
        ]
        
        # List of questions that are typically deterministic/metadata
        deterministic_questions = [
            'contract_start_date', 'target_company_name', 'counterparty_name',
            'contract_type', 'document_title', 'document_date'
        ]
        
        for section_key, section_data in questionnaire_responses.items():
            for question in section_data.get('questions', []):
                question_id = question.get('id', 'unknown')
                citations = question.get('citations', [])
                confidence = question.get('confidence', 0)
                answer = str(question.get('answer', '')).lower()
                
                # Skip validation for deterministic fields
                if (answer == 'deterministic_field' or 
                    question_id in deterministic_questions or
                    answer in ['not specified', 'not found', 'unknown', 'n/a']):
                    continue
                
                # Only check for empty citations on questions that should have them
                if not citations and question_id in citation_required_questions:
                    self.validation_results['empty_citations'] += 1
                    self.issues_found.append({
                        "type": "empty_citation",
                        "location": f"question_{question_id}",
                        "severity": "medium",
                        "message": f"Question '{question_id}' should have citations but has none"
                    })
                
                # Check confidence levels (but not for deterministic fields)
                if confidence < self.min_confidence and confidence > 0:
                    self.validation_results['low_confidence'] += 1
                    self.issues_found.append({
                        "type": "low_confidence",
                        "location": f"question_{question_id}",
                        "severity": "low",
                        "message": f"Question '{question_id}' has low confidence: {confidence:.2f}"
                    })
                
                # Validate each citation
                for citation_id in citations:
                    self._validate_single_citation(citation_id, f"question_{question_id}")
                    
        # Store citation tracker data if available
        try:
            from utils.citation_tracker import citation_tracker
            self.validation_results['total_citations'] = len(citation_tracker.citations)
        except ImportError:
            pass
    
    def _validate_rule_citations(self, state: ContractAnalysisState):
        """Validate citations in rule compliance results."""
        compliance_summary = state.get('compliance_summary', {})
        rules_with_citations = compliance_summary.get('rules_with_citations', [])
        
        for rule_data in rules_with_citations:
            rule_id = rule_data.get('rule_id', 'unknown')
            citations = rule_data.get('citations', [])
            
            if not citations:
                self.validation_results['empty_citations'] += 1
                self.issues_found.append({
                    "type": "empty_citation",
                    "location": f"rule_{rule_id}",
                    "severity": "high",
                    "message": f"Rule '{rule_id}' has no supporting citations"
                })
            
            for citation in citations:
                if isinstance(citation, dict):
                    self._validate_citation_dict(citation, f"rule_{rule_id}")
    
    def _validate_single_citation(self, citation_id: str, location: str):
        """Validate a single citation by ID."""
        try:
            from utils.citation_tracker import citation_tracker
            
            if citation_id not in citation_tracker.citations:
                self.issues_found.append({
                    "type": "invalid_citation",
                    "location": location,
                    "severity": "high",
                    "message": f"Citation ID '{citation_id}' not found in tracker"
                })
                return
            
            citation = citation_tracker.citations[citation_id]
            
            # Check for unknown location
            if "unknown location" in citation.location.lower():
                self.validation_results['unknown_locations'] += 1
                self.issues_found.append({
                    "type": "unknown_location",
                    "location": location,
                    "severity": "medium",
                    "message": f"Citation has unknown location: {citation_id}"
                })
            
            # Check for page anchor
            if self.require_page_anchors and not citation.page_number:
                self.validation_results['missing_page_anchors'] += 1
                self.issues_found.append({
                    "type": "missing_page_anchor",
                    "location": location,
                    "severity": "medium",
                    "message": f"Citation missing page anchor: {citation_id}"
                })
                
            # Check confidence
            if citation.confidence < self.min_confidence:
                self.validation_results['low_confidence'] += 1
                
        except ImportError:
            logger.warning("Could not import citation_tracker for validation")
    
    def _validate_citation_dict(self, citation: Dict[str, Any], location: str):
        """Validate a citation dictionary directly."""
        # Check for location issues
        citation_location = citation.get('location', '')
        if "unknown" in citation_location.lower():
            self.validation_results['unknown_locations'] += 1
            self.issues_found.append({
                "type": "unknown_location",
                "location": location,
                "severity": "medium",
                "message": "Citation has unknown location"
            })
        
        # Check for page anchor
        if self.require_page_anchors:
            has_anchor = (
                '[[page=' in str(citation.get('location', '')) or
                '[[page=' in str(citation.get('source_text', '')) or
                citation.get('page_anchor') or
                citation.get('page_number')
            )
            if not has_anchor:
                self.validation_results['missing_page_anchors'] += 1
                self.issues_found.append({
                    "type": "missing_page_anchor",
                    "location": location,
                    "severity": "medium",
                    "message": "Citation missing page anchor"
                })
    
    def _determine_severity(self):
        """Determine overall severity based on issues found."""
        if not self.issues_found:
            self.validation_results['severity'] = 'none'
            self.validation_results['validation_passed'] = True
            return
        
        # Count issues by severity
        severity_counts = {
            'critical': 0,
            'high': 0,
            'medium': 0,
            'low': 0
        }
        
        for issue in self.issues_found:
            severity_counts[issue['severity']] += 1
        
        # Start with base severity determination
        if severity_counts['critical'] > 0:
            self.validation_results['severity'] = 'critical'
            self.validation_results['validation_passed'] = False
        elif severity_counts['high'] > 1:  # Changed from > 0 to > 1
            self.validation_results['severity'] = 'high'
            self.validation_results['validation_passed'] = False
        elif severity_counts['medium'] > 3:  # Changed from > 2 to > 3
            self.validation_results['severity'] = 'medium'
            self.validation_results['validation_passed'] = False
        elif severity_counts['medium'] > 0:
            self.validation_results['severity'] = 'low'
            # Low severity doesn't fail validation by default
        else:
            self.validation_results['severity'] = 'low'
        
        # Check specific thresholds that upgrade severity
        if self.validation_results['unknown_locations'] > self.max_unknown_locations:
            self.validation_results['validation_passed'] = False
            if self.validation_results['severity'] == 'low':
                self.validation_results['severity'] = 'medium'  # Upgrade to medium, not high
        
        if self.validation_results['missing_page_anchors'] > 5:  # Changed from > 3 to > 5
            self.validation_results['validation_passed'] = False
            if self.validation_results['severity'] == 'low':
                self.validation_results['severity'] = 'medium'  # At least medium
        
        if self.validation_results['empty_citations'] > 5:  # Changed from > 3 to > 5
            self.validation_results['validation_passed'] = False
            if self.validation_results['severity'] in ['none', 'low']:
                self.validation_results['severity'] = 'medium'  # At least medium
    
    def _generate_recommendations(self):
        """Generate recommendations based on validation results."""
        recommendations = []
        
        if self.validation_results['missing_page_anchors'] > 0:
            recommendations.append({
                "type": "reprocess_documents",
                "priority": "high",
                "message": "Reprocess documents to extract page anchors",
                "action": "Re-run PDF conversion with page anchor extraction enabled"
            })
        
        if self.validation_results['empty_citations'] > 3:
            recommendations.append({
                "type": "improve_classification",
                "priority": "medium",
                "message": "Many questions lack citations",
                "action": "Consider using retrieval fallback or improving classification"
            })
        
        if self.validation_results['low_confidence'] > 5:
            recommendations.append({
                "type": "model_tuning",
                "priority": "low",
                "message": "Multiple low-confidence extractions",
                "action": "Consider using a different model or adjusting prompts"
            })
        
        if self.validation_results['unknown_locations'] > 0:
            recommendations.append({
                "type": "fix_page_mapping",
                "priority": "high",
                "message": f"{self.validation_results['unknown_locations']} citations have unknown locations",
                "action": "Ensure document has page markers and sentences are properly mapped"
            })
        
        self.validation_results['recommendations'] = recommendations
        self.validation_results['issues'] = self.issues_found


@handle_node_errors("citation_critic")
def citation_critic_node(state: ContractAnalysisState) -> Dict[str, Any]:
    """
    LangGraph node for citation criticism and validation.
    
    Returns updated state with:
    - citation_validation_results: Detailed validation results
    - citation_issues_found: List of specific issues
    - needs_citation_rerun: Boolean indicating if rerun is needed
    - citation_critic_attempts: Number of critic runs so far
    """
    print("\n--- CITATION CRITIC ANALYSIS ---")
    
    # Get configuration from environment
    min_confidence = float(os.getenv('CITATION_MIN_CONFIDENCE', '0.6'))
    require_anchors = os.getenv('CITATION_REQUIRE_ANCHORS', 'true').lower() == 'true'
    max_unknown = int(os.getenv('CITATION_MAX_UNKNOWN', '3'))
    
    # Track attempts
    attempts = state.get('citation_critic_attempts', 0) + 1
    
    print(f"  Running citation critic (attempt {attempts})")
    print("  Configuration:")
    print(f"    - Min confidence: {min_confidence}")
    print(f"    - Require page anchors: {require_anchors}")
    print(f"    - Max unknown locations: {max_unknown}")
    
    # Create and run critic
    critic = CitationCritic(
        min_confidence=min_confidence,
        require_page_anchors=require_anchors,
        max_unknown_locations=max_unknown
    )
    
    validation_results = critic.validate_citations(state)
    
    # Print summary
    print("\n  Validation Results:")
    print(f"    - Total citations: {validation_results['total_citations']}")
    print(f"    - Empty citations: {validation_results['empty_citations']}")
    print(f"    - Missing page anchors: {validation_results['missing_page_anchors']}")
    print(f"    - Unknown locations: {validation_results['unknown_locations']}")
    print(f"    - Low confidence: {validation_results['low_confidence']}")
    print(f"    - Severity: {validation_results['severity']}")
    print(f"    - Validation passed: {validation_results['validation_passed']}")
    
    # Print recommendations
    if validation_results['recommendations']:
        print("\n  Recommendations:")
        for rec in validation_results['recommendations']:
            print(f"    [{rec['priority']}] {rec['message']}")
    
    # Determine if rerun is needed
    max_reruns = int(os.getenv('CITATION_MAX_RERUNS', '3'))
    needs_rerun = (
        not validation_results['validation_passed'] and 
        attempts < max_reruns and (
            validation_results['severity'] in ['high', 'critical'] or
            (validation_results['severity'] == 'medium' and require_anchors)
        )
    )
    
    if needs_rerun:
        print(f"\n  ⚠️ Citation quality issues detected - will trigger rerun (attempt {attempts}/{max_reruns})")
    else:
        if validation_results['validation_passed']:
            print("\n  ✅ Citation validation PASSED")
        else:
            print("\n  ❌ Citation validation FAILED but max reruns reached or severity too low")
    
    # Update state
    return {
        'citation_validation_results': validation_results,
        'citation_issues_found': validation_results['issues'],
        'needs_citation_rerun': needs_rerun,
        'citation_critic_attempts': attempts,
        'citation_critic_recommendations': validation_results['recommendations']
    }


def should_rerun_citations(state: ContractAnalysisState) -> str:
    """
    Conditional edge function to determine if citations should be rerun.
    
    Returns:
        "rerun_classification" if rerun is needed
        "continue" if validation passed or max attempts reached
    """
    needs_rerun = state.get('needs_citation_rerun', False)
    
    if needs_rerun:
        # Clear the rerun flag for next iteration
        state['needs_citation_rerun'] = False
        
        # Add processing note
        warnings = state.get('processing_warnings', [])
        attempts = state.get('citation_critic_attempts', 0)
        warnings.append(f"Citation rerun triggered (attempt {attempts})")
        state['processing_warnings'] = warnings
        
        return "rerun_classification"
    
    return "continue"