"""
Questionnaire Completeness Critic Agent
Validates questionnaire answer quality and triggers targeted retries
"""

import os
from typing import Dict, Any, List, Optional
from workflows.state import ContractAnalysisState
from utils.error_handler import handle_node_errors
import logging

logger = logging.getLogger(__name__)


class QuestionnaireCompletenessCritic:
    """
    Validates questionnaire completeness and quality.
    Checks for:
    - Percentage of "Not specified" answers
    - Contradictory answers
    - Required fields that are empty
    - Suspicious patterns (all same answer)
    - Low confidence answers
    - Risk questions without assessments
    """
    
    def __init__(self,
                 max_not_specified_ratio: float = 0.4,
                 min_confidence: float = 0.6,
                 required_fields: Optional[List[str]] = None,
                 risk_questions: Optional[List[str]] = None):
        """
        Initialize the questionnaire critic.
        
        Args:
            max_not_specified_ratio: Maximum acceptable ratio of "Not specified" answers
            min_confidence: Minimum confidence for answers
            required_fields: List of required question IDs
            risk_questions: List of questions requiring risk assessment
        """
        self.max_not_specified_ratio = max_not_specified_ratio
        self.min_confidence = min_confidence
        self.required_fields = required_fields or [
            'contract_start_date', 'target_company_name', 'counterparty_name',
            'governing_law', 'term', 'termination'
        ]
        self.risk_questions = risk_questions or [
            'limitation_of_liability', 'indemnity', 'ip_rights',
            'assignment_coc', 'exclusivity_non_competes', 'forced_pricing_adjustments'
        ]
        self.validation_results = {}
        self.issues_found = []
    
    def validate_questionnaire(self, state: ContractAnalysisState) -> Dict[str, Any]:
        """
        Validate questionnaire completeness and quality.
        
        Returns:
            Dict containing validation results and recommendations
        """
        self.validation_results = {
            "total_questions": 0,
            "answered_questions": 0,
            "not_specified_count": 0,
            "not_specified_ratio": 0.0,
            "low_confidence_count": 0,
            "missing_required": [],
            "contradictions": [],
            "suspicious_patterns": [],
            "risk_without_assessment": [],
            "average_confidence": 0.0,
            "sections_analyzed": [],
            "validation_passed": True,
            "issues": [],
            "recommendations": [],
            "severity": "none",
            "questions_to_retry": []
        }
        self.issues_found = []
        
        # Get questionnaire responses
        questionnaire_responses = state.get('questionnaire_responses', {})
        
        if not questionnaire_responses:
            self.issues_found.append({
                "type": "no_responses",
                "severity": "critical",
                "message": "No questionnaire responses found"
            })
            self.validation_results['severity'] = 'critical'
            self.validation_results['validation_passed'] = False
            self.validation_results['issues'] = self.issues_found
            return self.validation_results
        
        # Analyze each section
        all_answers = {}
        for section_key, section_data in questionnaire_responses.items():
            self.validation_results['sections_analyzed'].append(section_key)
            
            for question in section_data.get('questions', []):
                question_id = question.get('id', 'unknown')
                answer = question.get('answer', '')
                confidence = question.get('confidence', 0)
                
                all_answers[question_id] = {
                    'answer': answer,
                    'confidence': confidence,
                    'section': section_key,
                    'has_risk_assessment': bool(question.get('risk_assessment')),
                    'citations': question.get('citations', [])
                }
        
        # Perform validations
        self._check_completeness(all_answers)
        self._check_required_fields(all_answers)
        self._check_confidence_levels(all_answers)
        self._detect_contradictions(all_answers)
        self._detect_patterns(all_answers)
        self._check_risk_assessments(all_answers)
        
        # Identify questions to retry
        self._identify_retry_questions(all_answers)
        
        # Determine severity
        self._determine_severity()
        
        # Generate recommendations
        self._generate_recommendations()
        
        return self.validation_results
    
    def _check_completeness(self, answers: Dict[str, Dict]):
        """Check overall answer completeness."""
        total = len(answers)
        not_specified = 0
        answered = 0
        
        for question_id, data in answers.items():
            answer = str(data['answer']).lower()
            
            if answer in ['not specified', 'not found', 'unknown', '', 'n/a']:
                not_specified += 1
            elif answer != 'deterministic_field':
                answered += 1
            
        self.validation_results['total_questions'] = total
        self.validation_results['answered_questions'] = answered
        self.validation_results['not_specified_count'] = not_specified
        
        ratio = not_specified / total if total > 0 else 0
        self.validation_results['not_specified_ratio'] = ratio
        
        if ratio > self.max_not_specified_ratio:
            self.issues_found.append({
                "type": "too_many_not_specified",
                "severity": "high",
                "message": f"{ratio:.1%} of answers are 'Not specified' (max: {self.max_not_specified_ratio:.1%})"
            })
    
    def _check_required_fields(self, answers: Dict[str, Dict]):
        """Check if required fields are answered."""
        missing = []
        
        for field_id in self.required_fields:
            if field_id in answers:
                answer = str(answers[field_id]['answer']).lower()
                if answer in ['not specified', 'not found', 'unknown', '', 'n/a']:
                    missing.append(field_id)
            else:
                missing.append(field_id)
        
        self.validation_results['missing_required'] = missing
        
        if missing:
            self.issues_found.append({
                "type": "missing_required_fields",
                "severity": "high",
                "message": f"Required fields missing: {', '.join(missing[:3])}"
            })
    
    def _check_confidence_levels(self, answers: Dict[str, Dict]):
        """Check confidence levels of answers."""
        confidences = []
        low_conf_questions = []
        
        for question_id, data in answers.items():
            confidence = data['confidence']
            answer = str(data['answer']).lower()
            
            # Skip deterministic fields
            if answer == 'deterministic_field':
                continue
            
            confidences.append(confidence)
            
            if confidence < self.min_confidence and confidence > 0:
                low_conf_questions.append(question_id)
        
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0
        self.validation_results['average_confidence'] = avg_confidence
        self.validation_results['low_confidence_count'] = len(low_conf_questions)
        
        if avg_confidence < self.min_confidence:
            self.issues_found.append({
                "type": "low_average_confidence",
                "severity": "medium",
                "message": f"Average confidence {avg_confidence:.2f} below minimum {self.min_confidence}"
            })
        
        if len(low_conf_questions) > len(answers) * 0.3:
            self.issues_found.append({
                "type": "many_low_confidence",
                "severity": "medium",
                "message": f"{len(low_conf_questions)} questions have low confidence"
            })
    
    def _detect_contradictions(self, answers: Dict[str, Dict]):
        """Detect contradictory answers."""
        contradictions = []
        
        # Check for specific contradiction patterns
        contradiction_pairs = [
            ('unlimited_liability', 'limitation_of_liability'),
            ('exclusive_agreement', 'non_exclusive_agreement'),
            ('perpetual_term', 'fixed_term'),
            ('assignment_allowed', 'assignment_prohibited')
        ]
        
        for pair in contradiction_pairs:
            if pair[0] in answers and pair[1] in answers:
                answer1 = str(answers[pair[0]]['answer']).lower()
                answer2 = str(answers[pair[1]]['answer']).lower()
                
                # Check if both are affirmative (potential contradiction)
                affirmative_words = ['yes', 'true', 'present', 'exists', 'included']
                if any(word in answer1 for word in affirmative_words) and \
                   any(word in answer2 for word in affirmative_words):
                    contradictions.append(f"{pair[0]} vs {pair[1]}")
        
        # Check term vs termination contradiction
        if 'term' in answers and 'termination' in answers:
            term_answer = str(answers['term']['answer']).lower()
            termination_answer = str(answers['termination']['answer']).lower()
            
            if 'perpetual' in term_answer and 'immediate' in termination_answer:
                contradictions.append("perpetual term vs immediate termination")
        
        self.validation_results['contradictions'] = contradictions
        
        if contradictions:
            self.issues_found.append({
                "type": "contradictory_answers",
                "severity": "high",
                "message": f"Contradictions detected: {'; '.join(contradictions[:2])}"
            })
    
    def _detect_patterns(self, answers: Dict[str, Dict]):
        """Detect suspicious answer patterns."""
        patterns = []
        
        # Group answers by text
        answer_groups = {}
        for question_id, data in answers.items():
            answer = str(data['answer']).lower()
            if answer not in ['deterministic_field', '']:
                if answer not in answer_groups:
                    answer_groups[answer] = []
                answer_groups[answer].append(question_id)
        
        # Check for repeated answers
        for answer_text, questions in answer_groups.items():
            if len(questions) > 5 and len(questions) > len(answers) * 0.3:
                patterns.append(f"'{answer_text[:30]}' repeated {len(questions)} times")
        
        # Check if all answers are very short
        short_answers = sum(1 for _, data in answers.items() 
                          if len(str(data['answer'])) < 20 and 
                          str(data['answer']).lower() != 'deterministic_field')
        if short_answers > len(answers) * 0.7:
            patterns.append("Majority of answers are very short")
        
        self.validation_results['suspicious_patterns'] = patterns
        
        if patterns:
            self.issues_found.append({
                "type": "suspicious_patterns",
                "severity": "medium",
                "message": f"Suspicious patterns: {patterns[0]}"
            })
    
    def _check_risk_assessments(self, answers: Dict[str, Dict]):
        """Check if risk questions have assessments."""
        missing_assessments = []
        
        for risk_q in self.risk_questions:
            if risk_q in answers:
                data = answers[risk_q]
                answer = str(data['answer']).lower()
                
                # If question is answered but no risk assessment
                if (answer not in ['not specified', 'not found', 'unknown', '', 'n/a', 'deterministic_field'] 
                    and not data['has_risk_assessment']):
                    missing_assessments.append(risk_q)
        
        self.validation_results['risk_without_assessment'] = missing_assessments
        
        if missing_assessments:
            self.issues_found.append({
                "type": "missing_risk_assessments",
                "severity": "medium",
                "message": f"Risk questions without assessment: {', '.join(missing_assessments[:3])}"
            })
    
    def _identify_retry_questions(self, answers: Dict[str, Dict]):
        """Identify specific questions that should be retried."""
        retry_questions = []
        
        # Add required fields that are missing
        retry_questions.extend(self.validation_results['missing_required'])
        
        # Add very low confidence questions
        for question_id, data in answers.items():
            if data['confidence'] < 0.3 and data['confidence'] > 0:
                if question_id not in retry_questions:
                    retry_questions.append(question_id)
        
        # Add questions without citations (if not deterministic)
        for question_id, data in answers.items():
            answer = str(data['answer']).lower()
            if (answer != 'deterministic_field' and 
                answer not in ['not specified', 'not found'] and
                not data['citations']):
                if question_id not in retry_questions:
                    retry_questions.append(question_id)
        
        # Limit to top priority questions
        self.validation_results['questions_to_retry'] = retry_questions[:10]
    
    def _determine_severity(self):
        """Determine overall severity."""
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
        elif severity_counts['medium'] > 2:
            self.validation_results['severity'] = 'medium'
            self.validation_results['validation_passed'] = False
        else:
            self.validation_results['severity'] = 'low'
        
        # Special checks
        if self.validation_results['not_specified_ratio'] > 0.5:
            self.validation_results['severity'] = 'high'
            self.validation_results['validation_passed'] = False
        
        if len(self.validation_results['contradictions']) > 0:
            self.validation_results['severity'] = 'high'
            self.validation_results['validation_passed'] = False
        
        self.validation_results['issues'] = self.issues_found
    
    def _generate_recommendations(self):
        """Generate recommendations."""
        recommendations = []
        
        # Completeness recommendations
        if self.validation_results['not_specified_ratio'] > self.max_not_specified_ratio:
            recommendations.append({
                "type": "use_retrieval_fallback",
                "priority": "high",
                "message": "Too many unanswered questions",
                "action": "Enable retrieval fallback for better coverage"
            })
        
        # Confidence recommendations
        if self.validation_results['average_confidence'] < self.min_confidence:
            recommendations.append({
                "type": "improve_extraction",
                "priority": "medium",
                "message": "Low answer confidence",
                "action": "Use enhanced prompts or different model"
            })
        
        # Contradiction recommendations
        if self.validation_results['contradictions']:
            recommendations.append({
                "type": "resolve_contradictions",
                "priority": "high",
                "message": "Contradictory answers detected",
                "action": "Re-evaluate contradictory questions with context"
            })
        
        # Risk assessment recommendations
        if self.validation_results['risk_without_assessment']:
            recommendations.append({
                "type": "add_risk_assessments",
                "priority": "medium",
                "message": "Risk questions lack assessments",
                "action": "Run risk assessment for identified questions"
            })
        
        # Targeted retry recommendation
        if self.validation_results['questions_to_retry']:
            recommendations.append({
                "type": "targeted_retry",
                "priority": "high",
                "message": f"Retry {len(self.validation_results['questions_to_retry'])} specific questions",
                "action": "Use retrieval fallback for failed questions only"
            })
        
        self.validation_results['recommendations'] = recommendations


@handle_node_errors("questionnaire_completeness_critic")
def questionnaire_completeness_critic_node(state: ContractAnalysisState) -> Dict[str, Any]:
    """
    LangGraph node for questionnaire completeness validation.
    
    Returns updated state with:
    - questionnaire_validation_results: Detailed validation results
    - needs_questionnaire_rerun: Boolean indicating if rerun is needed
    - questionnaire_critic_attempts: Number of attempts so far
    - questionnaire_retry_config: Configuration for retry
    """
    print("\n--- QUESTIONNAIRE COMPLETENESS CRITIC ---")
    
    # Get configuration
    max_not_specified = float(os.getenv('QUESTIONNAIRE_MAX_NOT_SPECIFIED', '0.4'))
    min_confidence = float(os.getenv('QUESTIONNAIRE_MIN_CONFIDENCE', '0.6'))
    max_reruns = int(os.getenv('QUESTIONNAIRE_MAX_RERUNS', '2'))
    
    # Track attempts
    attempts = state.get('questionnaire_critic_attempts', 0) + 1
    
    print(f"  Running questionnaire critic (attempt {attempts})")
    print("  Configuration:")
    print(f"    - Max 'Not specified' ratio: {max_not_specified:.1%}")
    print(f"    - Min confidence: {min_confidence:.2f}")
    
    # Create and run critic
    critic = QuestionnaireCompletenessCritic(
        max_not_specified_ratio=max_not_specified,
        min_confidence=min_confidence
    )
    
    validation_results = critic.validate_questionnaire(state)
    
    # Print summary
    print("\n  Validation Results:")
    print(f"    - Questions analyzed: {validation_results['total_questions']}")
    print(f"    - Not specified: {validation_results['not_specified_ratio']:.1%}")
    print(f"    - Average confidence: {validation_results['average_confidence']:.2f}")
    print(f"    - Missing required: {len(validation_results['missing_required'])}")
    print(f"    - Contradictions: {len(validation_results['contradictions'])}")
    print(f"    - Severity: {validation_results['severity']}")
    print(f"    - Validation passed: {validation_results['validation_passed']}")
    
    # Determine if rerun is needed
    needs_rerun = (
        not validation_results['validation_passed'] and
        attempts < max_reruns and
        validation_results['severity'] in ['high', 'critical']
    )
    
    # Prepare retry configuration
    retry_config = {}
    if needs_rerun:
        print("\n  ⚠️ Questionnaire issues - preparing retry configuration")
        
        retry_config['use_retrieval_fallback'] = True
        retry_config['target_questions'] = validation_results['questions_to_retry']
        retry_config['enhance_prompts'] = True
        
        if validation_results['contradictions']:
            retry_config['resolve_contradictions'] = True
        
        print(f"    - Will retry {len(validation_results['questions_to_retry'])} questions")
        print("    - Using retrieval fallback")
        
        state['questionnaire_retry_config'] = retry_config
    else:
        if validation_results['validation_passed']:
            print("\n  ✅ Questionnaire validation PASSED")
        else:
            print("\n  ❌ Questionnaire validation FAILED but max reruns reached")
    
    return {
        'questionnaire_validation_results': validation_results,
        'needs_questionnaire_rerun': needs_rerun,
        'questionnaire_critic_attempts': attempts,
        'questionnaire_retry_config': retry_config
    }


def should_rerun_questionnaire(state: ContractAnalysisState) -> str:
    """
    Conditional edge function for questionnaire rerun.
    
    Returns:
        "retry_questionnaire" if rerun is needed
        "continue" if validation passed or max attempts reached
    """
    needs_rerun = state.get('needs_questionnaire_rerun', False)
    
    if needs_rerun:
        retry_config = state.get('questionnaire_retry_config', {})
        print(f"\n  Applying questionnaire retry configuration: {retry_config}")
        
        for key, value in retry_config.items():
            state[f'questionnaire_{key}'] = value
        
        return "retry_questionnaire"
    
    return "continue"