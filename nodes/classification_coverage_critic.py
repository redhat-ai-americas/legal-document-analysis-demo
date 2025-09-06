"""
Classification Coverage Critic Agent
Validates sentence classification quality and triggers retries with adjusted parameters
"""

import os
from typing import Dict, Any, List, Optional
from workflows.state import ContractAnalysisState
from utils.error_handler import handle_node_errors
import logging

logger = logging.getLogger(__name__)


class ClassificationCoverageCritic:
    """
    Validates classification coverage and quality.
    Checks for:
    - Sufficient percentage of classified sentences
    - Coverage of critical terminology terms
    - Confidence score distribution
    - Document type detection (amendments, addendums)
    - Expected sections coverage
    """
    
    def __init__(self,
                 min_coverage: float = 0.3,
                 min_confidence: float = 0.5,
                 critical_terms: Optional[List[str]] = None,
                 expected_sections: Optional[List[str]] = None):
        """
        Initialize the classification critic.
        
        Args:
            min_coverage: Minimum percentage of sentences that should be classified
            min_confidence: Minimum average confidence score
            critical_terms: List of terms that must be found
            expected_sections: List of sections that should be detected
        """
        self.min_coverage = min_coverage
        self.min_confidence = min_confidence
        self.critical_terms = critical_terms or [
            'termination', 'liability', 'indemnity', 'confidentiality',
            'payment', 'warranty', 'assignment', 'governing_law'
        ]
        self.expected_sections = expected_sections or [
            'terms', 'payment', 'liability', 'termination'
        ]
        self.validation_results = {}
        self.issues_found = []
    
    def validate_classification(self, state: ContractAnalysisState) -> Dict[str, Any]:
        """
        Validate classification quality and coverage.
        
        Returns:
            Dict containing validation results and recommendations
        """
        self.validation_results = {
            "total_sentences": 0,
            "classified_sentences": 0,
            "no_class_sentences": 0,
            "coverage_percentage": 0.0,
            "average_confidence": 0.0,
            "low_confidence_count": 0,
            "critical_terms_found": [],
            "critical_terms_missing": [],
            "sections_found": [],
            "document_type_indicators": [],
            "validation_passed": True,
            "issues": [],
            "recommendations": [],
            "severity": "none"
        }
        self.issues_found = []
        
        # Get classified sentences
        classified = state.get('classified_sentences', [])
        
        if not classified:
            self.issues_found.append({
                "type": "no_classifications",
                "severity": "critical",
                "message": "No sentences were classified"
            })
            self.validation_results['severity'] = 'critical'
            self.validation_results['validation_passed'] = False
            self.validation_results['issues'] = self.issues_found
            return self.validation_results
        
        # Analyze classification coverage
        self._analyze_coverage(classified)
        
        # Check critical terms
        self._check_critical_terms(classified)
        
        # Analyze confidence distribution
        self._analyze_confidence(classified)
        
        # Detect document type
        self._detect_document_type(classified, state)
        
        # Determine severity
        self._determine_severity()
        
        # Generate recommendations
        self._generate_recommendations()
        
        return self.validation_results
    
    def _analyze_coverage(self, classified: List[Dict[str, Any]]):
        """Analyze classification coverage statistics."""
        total = len(classified)
        self.validation_results['total_sentences'] = total
        
        classified_count = 0
        no_class_count = 0
        
        for sentence_data in classified:
            classes = sentence_data.get('classes', [])
            
            if not classes or 'no-class' in classes or 'none' in classes:
                no_class_count += 1
            else:
                classified_count += 1
        
        self.validation_results['classified_sentences'] = classified_count
        self.validation_results['no_class_sentences'] = no_class_count
        
        coverage = classified_count / total if total > 0 else 0
        self.validation_results['coverage_percentage'] = coverage
        
        # Check if coverage is too low
        if coverage < self.min_coverage:
            self.issues_found.append({
                "type": "low_coverage",
                "severity": "high",
                "message": f"Only {coverage:.1%} of sentences classified (minimum: {self.min_coverage:.1%})"
            })
    
    def _check_critical_terms(self, classified: List[Dict[str, Any]]):
        """Check if critical terms are covered."""
        found_terms = set()
        
        for sentence_data in classified:
            classes = sentence_data.get('classes', [])
            for term in classes:
                if term and term != 'no-class' and term != 'none':
                    # Normalize term name
                    term_normalized = term.lower().replace('-', '_').replace(' ', '_')
                    found_terms.add(term_normalized)
        
        # Check critical terms
        critical_found = []
        critical_missing = []
        
        for critical_term in self.critical_terms:
            term_normalized = critical_term.lower().replace('-', '_').replace(' ', '_')
            if term_normalized in found_terms:
                critical_found.append(critical_term)
            else:
                critical_missing.append(critical_term)
        
        self.validation_results['critical_terms_found'] = critical_found
        self.validation_results['critical_terms_missing'] = critical_missing
        
        # Flag if too many critical terms are missing
        if len(critical_missing) > len(self.critical_terms) * 0.5:
            self.issues_found.append({
                "type": "missing_critical_terms",
                "severity": "high",
                "message": f"Missing {len(critical_missing)} critical terms: {', '.join(critical_missing[:3])}..."
            })
    
    def _analyze_confidence(self, classified: List[Dict[str, Any]]):
        """Analyze confidence score distribution."""
        confidences = []
        low_conf_count = 0
        
        for sentence_data in classified:
            confidence = sentence_data.get('confidence', 0)
            confidences.append(confidence)
            
            if confidence < self.min_confidence and confidence > 0:
                low_conf_count += 1
        
        # Calculate average confidence
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0
        self.validation_results['average_confidence'] = avg_confidence
        self.validation_results['low_confidence_count'] = low_conf_count
        
        # Check if confidence is too low overall
        if avg_confidence < self.min_confidence:
            self.issues_found.append({
                "type": "low_confidence",
                "severity": "medium",
                "message": f"Average confidence {avg_confidence:.2f} below minimum {self.min_confidence}"
            })
        
        # Check if too many low confidence
        if low_conf_count > len(classified) * 0.3:
            self.issues_found.append({
                "type": "many_low_confidence",
                "severity": "medium",
                "message": f"{low_conf_count} sentences have low confidence (30% threshold)"
            })
    
    def _detect_document_type(self, classified: List[Dict[str, Any]], state: ContractAnalysisState):
        """Detect special document types that need different handling."""
        document_text = state.get('document_text', '').lower()
        
        indicators = []
        
        # Check for amendment
        if 'amendment' in document_text or 'addendum' in document_text:
            indicators.append('amendment')
            
            # Check if classification caught amendment-specific content
            amendment_terms = ['modification', 'amendment', 'addendum', 'supplement']
            found_amendment = False
            
            for sentence_data in classified:
                classes = sentence_data.get('classes', [])
                if any(term in str(classes).lower() for term in amendment_terms):
                    found_amendment = True
                    break
            
            if not found_amendment:
                self.issues_found.append({
                    "type": "amendment_not_classified",
                    "severity": "medium",
                    "message": "Document appears to be amendment but not classified as such"
                })
        
        # Check for short document
        if len(classified) < 20:
            indicators.append('short_document')
            self.issues_found.append({
                "type": "short_document",
                "severity": "low",
                "message": f"Document is very short ({len(classified)} sentences)"
            })
        
        self.validation_results['document_type_indicators'] = indicators
    
    def _determine_severity(self):
        """Determine overall severity based on issues."""
        if not self.issues_found:
            self.validation_results['severity'] = 'none'
            return
        
        severity_counts = {
            'critical': 0,
            'high': 0,
            'medium': 0,
            'low': 0
        }
        
        for issue in self.issues_found:
            severity_counts[issue['severity']] += 1
        
        # Determine overall severity
        if severity_counts['critical'] > 0:
            self.validation_results['severity'] = 'critical'
            self.validation_results['validation_passed'] = False
        elif severity_counts['high'] > 0:
            self.validation_results['severity'] = 'high'
            self.validation_results['validation_passed'] = False
        elif severity_counts['medium'] > 1:
            self.validation_results['severity'] = 'medium'
            self.validation_results['validation_passed'] = False
        elif severity_counts['medium'] > 0:
            self.validation_results['severity'] = 'low'
        else:
            self.validation_results['severity'] = 'low'
        
        # Special case: very low coverage always fails
        if self.validation_results['coverage_percentage'] < 0.1:
            self.validation_results['validation_passed'] = False
            self.validation_results['severity'] = 'critical'
        
        self.validation_results['issues'] = self.issues_found
    
    def _generate_recommendations(self):
        """Generate recommendations for improving classification."""
        recommendations = []
        
        # Coverage recommendations
        if self.validation_results['coverage_percentage'] < self.min_coverage:
            recommendations.append({
                "type": "adjust_thresholds",
                "priority": "high",
                "message": "Lower classification confidence threshold to increase coverage",
                "action": "Set confidence_threshold=0.5 in classifier"
            })
            
            if self.validation_results['coverage_percentage'] < 0.1:
                recommendations.append({
                    "type": "use_fallback",
                    "priority": "critical",
                    "message": "Enable retrieval fallback for better coverage",
                    "action": "Set retrieval_fallback=True"
                })
        
        # Confidence recommendations
        if self.validation_results['average_confidence'] < self.min_confidence:
            recommendations.append({
                "type": "improve_prompts",
                "priority": "medium",
                "message": "Classification confidence is low",
                "action": "Consider using enhanced prompts or different model"
            })
        
        # Missing terms recommendations
        if self.validation_results['critical_terms_missing']:
            recommendations.append({
                "type": "expand_search",
                "priority": "high",
                "message": f"Critical terms missing: {', '.join(self.validation_results['critical_terms_missing'][:3])}",
                "action": "Use keyword search fallback for missing terms"
            })
        
        # Document type recommendations
        if 'amendment' in self.validation_results['document_type_indicators']:
            recommendations.append({
                "type": "amendment_mode",
                "priority": "medium",
                "message": "Document is an amendment",
                "action": "Use relaxed classification for amendment documents"
            })
        
        self.validation_results['recommendations'] = recommendations


@handle_node_errors("classification_coverage_critic")
def classification_coverage_critic_node(state: ContractAnalysisState) -> Dict[str, Any]:
    """
    LangGraph node for classification coverage validation.
    
    Returns updated state with:
    - classification_validation_results: Detailed validation results
    - needs_classification_rerun: Boolean indicating if rerun is needed
    - classification_critic_attempts: Number of attempts so far
    - classification_retry_config: Configuration adjustments for retry
    """
    print("\n--- CLASSIFICATION COVERAGE CRITIC ---")
    
    # Get configuration
    min_coverage = float(os.getenv('CLASSIFICATION_MIN_COVERAGE', '0.3'))
    min_confidence = float(os.getenv('CLASSIFICATION_MIN_CONFIDENCE', '0.5'))
    max_reruns = int(os.getenv('CLASSIFICATION_MAX_RERUNS', '2'))
    
    # Track attempts
    attempts = state.get('classification_critic_attempts', 0) + 1
    
    print(f"  Running classification critic (attempt {attempts})")
    print("  Configuration:")
    print(f"    - Min coverage: {min_coverage:.1%}")
    print(f"    - Min confidence: {min_confidence:.2f}")
    
    # Create and run critic
    critic = ClassificationCoverageCritic(
        min_coverage=min_coverage,
        min_confidence=min_confidence
    )
    
    validation_results = critic.validate_classification(state)
    
    # Print summary
    print("\n  Validation Results:")
    print(f"    - Coverage: {validation_results['coverage_percentage']:.1%} ({validation_results['classified_sentences']}/{validation_results['total_sentences']})")
    print(f"    - Average confidence: {validation_results['average_confidence']:.2f}")
    print(f"    - Critical terms found: {len(validation_results['critical_terms_found'])}/{len(critic.critical_terms)}")
    print(f"    - Severity: {validation_results['severity']}")
    print(f"    - Validation passed: {validation_results['validation_passed']}")
    
    # Print issues
    if validation_results['issues']:
        print("\n  Issues Found:")
        for issue in validation_results['issues'][:3]:
            print(f"    [{issue['severity']}] {issue['message']}")
    
    # Determine if rerun is needed
    needs_rerun = (
        not validation_results['validation_passed'] and
        attempts < max_reruns and
        validation_results['severity'] in ['high', 'critical']
    )
    
    # Prepare retry configuration if needed
    retry_config = {}
    if needs_rerun:
        print("\n  ⚠️ Classification quality issues - preparing retry configuration")
        
        # Adjust parameters for retry based on issues
        if validation_results['coverage_percentage'] < 0.2:
            retry_config['confidence_threshold'] = 0.4  # Lower threshold
            retry_config['use_efficient_mode'] = True
            retry_config['batch_size'] = 10
            print("    - Lowering confidence threshold to 0.4")
        
        if validation_results['critical_terms_missing']:
            retry_config['enable_retrieval_fallback'] = True
            print("    - Enabling retrieval fallback for missing terms")
        
        if 'amendment' in validation_results['document_type_indicators']:
            retry_config['is_amendment'] = True
            print("    - Using amendment mode")
        
        state['classification_retry_config'] = retry_config
    else:
        if validation_results['validation_passed']:
            print("\n  ✅ Classification validation PASSED")
        else:
            print("\n  ❌ Classification validation FAILED but max reruns reached")
    
    return {
        'classification_validation_results': validation_results,
        'needs_classification_rerun': needs_rerun,
        'classification_critic_attempts': attempts,
        'classification_retry_config': retry_config
    }


def should_rerun_classification(state: ContractAnalysisState) -> str:
    """
    Conditional edge function to determine if classification should be rerun.
    
    Returns:
        "retry_classification" if rerun is needed
        "continue" if validation passed or max attempts reached
    """
    needs_rerun = state.get('needs_classification_rerun', False)
    
    if needs_rerun:
        # Apply retry configuration
        retry_config = state.get('classification_retry_config', {})
        print(f"\n  Applying retry configuration: {retry_config}")
        
        # These would be used by the classifier on retry
        for key, value in retry_config.items():
            state[f'retry_{key}'] = value
        
        return "retry_classification"
    
    return "continue"