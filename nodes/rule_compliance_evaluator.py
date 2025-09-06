#!/usr/bin/env python3
"""
Rule Compliance Evaluator

Systematically evaluates all rules against a target document to determine compliance status.
This replaces the retrieval-based approach with a deterministic evaluation of every rule.
"""

import os
import json
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

from nodes.base_node import BatchProcessingNode
from utils.granite_client import GraniteClient
from utils.model_config import ModelConfig
from utils.retrieval_cache import RetrievalCache
from utils.classification_utils import load_prompt_template
from utils.classification_output_writer import save_rule_evaluation_results


class ComplianceStatus(Enum):
    """Rule compliance statuses"""
    COMPLIANT = "compliant"
    NON_COMPLIANT = "non_compliant"
    PARTIALLY_COMPLIANT = "partially_compliant"
    NOT_APPLICABLE = "not_applicable"
    REQUIRES_REVIEW = "requires_review"


@dataclass
class RuleEvaluation:
    """Result of evaluating a single rule"""
    rule_id: str
    rule_name: str
    status: ComplianceStatus
    confidence: float
    rationale: str
    evidence: List[Dict[str, Any]] = field(default_factory=list)
    severity: str = "medium"
    exceptions_applied: List[str] = field(default_factory=list)
    relevant_sections: List[str] = field(default_factory=list)
    citations: List[Dict[str, Any]] = field(default_factory=list)


class RuleComplianceEvaluator(BatchProcessingNode):
    """Evaluates all rules against a target document"""
    
    def __init__(self):
        """Initialize the rule compliance evaluator"""
        super().__init__(node_name="RuleComplianceEvaluator", batch_size=5)
        self.model_config = ModelConfig()
        self.granite_client = GraniteClient()
        self.retrieval_cache = RetrievalCache()
        
        # Configuration
        self.min_confidence = float(os.getenv('RULE_MIN_CONFIDENCE', '0.6'))
    
    def process(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process method required by BaseNode - delegates to evaluate_document_compliance
        
        Args:
            state: The workflow state
            
        Returns:
            Updated workflow state
        """
        return evaluate_document_compliance(state)
        
    def load_rules(self, rules_path: str) -> List[Dict[str, Any]]:
        """Load rules from file"""
        if not os.path.exists(rules_path):
            raise FileNotFoundError(f"Rules file not found: {rules_path}")
            
        with open(rules_path, 'r') as f:
            if rules_path.endswith('.json'):
                data = json.load(f)
                return data.get('rules', [])
            elif rules_path.endswith('.yaml') or rules_path.endswith('.yml'):
                import yaml
                data = yaml.safe_load(f)
                return data.get('rules', [])
            else:
                raise ValueError(f"Unsupported rules file format: {rules_path}")
    
    def find_relevant_sections(self, 
                             document_text: str, 
                             rule: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Find document sections relevant to a rule"""
        keywords = rule.get('keywords', [])
        if not keywords:
            return []
            
        relevant_sections = []
        sentences = document_text.split('.')
        
        for idx, sentence in enumerate(sentences):
            sentence_lower = sentence.lower()
            # Check if any keyword appears in the sentence
            if any(keyword.lower() in sentence_lower for keyword in keywords):
                # Get surrounding context (previous and next sentence)
                start_idx = max(0, idx - 1)
                end_idx = min(len(sentences), idx + 2)
                context = '. '.join(sentences[start_idx:end_idx])
                
                relevant_sections.append({
                    'sentence_id': idx,
                    'text': sentence.strip(),
                    'context': context.strip(),
                    'matched_keywords': [kw for kw in keywords if kw.lower() in sentence_lower]
                })
        
        return relevant_sections[:10]  # Limit to top 10 most relevant sections
    
    def evaluate_single_rule(self,
                           rule: Dict[str, Any],
                           document_text: str,
                           relevant_sections: List[Dict[str, Any]]) -> RuleEvaluation:
        """Evaluate a single rule against the document"""
        
        rule_id = rule.get('id', 'unknown')
        rule_name = rule.get('name', rule_id)
        rule_text = rule.get('rule_text', '')
        rule.get('default_status', 'non_compliant')
        severity = rule.get('severity', 'medium')
        exceptions = rule.get('exceptions', [])
        
        # If no relevant sections found, use default status
        if not relevant_sections:
            return RuleEvaluation(
                rule_id=rule_id,
                rule_name=rule_name,
                status=ComplianceStatus.NOT_APPLICABLE,
                confidence=0.9,
                rationale=f"No sections in the document appear to address {rule_name}",
                severity=severity
            )
        
        # Prepare context for evaluation
        context_text = '\n'.join([s['context'] for s in relevant_sections[:5]])
        
        # Create evaluation prompt with system message
        system_message, user_prompt = self._create_evaluation_prompt(
            rule_name, rule_text, context_text, exceptions
        )
        
        try:
            # Report that we're starting LLM analysis
            model_name = self.granite_client.model_name
            self.report_progress(
                f"🤖 Calling {model_name} for rule: {rule_name}",
                details={
                    'model': model_name,
                    'rule': rule_name,
                    'phase': 'llm_start'
                }
            )
            
            # Call LLM with system message (no streaming for simpler UI)
            response = self.granite_client.call_api_with_system_message(
                system_message,
                user_prompt,
                temperature=0.1,
                max_tokens=500,
                return_metadata=True
            )
            
            # Extract content
            if isinstance(response, dict) and 'content' in response:
                content = response['content']
                model_used = response.get('metadata', {}).get('model', model_name)
            else:
                content = response
                model_used = model_name
            
            # Report complete response with model info
            self.report_progress(
                f"✅ {model_used} completed analysis for: {rule_name}",
                details={
                    'model': model_used,
                    'rule': rule_name,
                    'phase': 'llm_complete',
                    'full_response': content
                }
            )
            
            # Display formatted analysis result to console
            print(f"\n{'─' * 60}")
            print(f"🤖 {model_used} Analysis for '{rule_name}':")
            print(f"{'─' * 60}")
            
            # Try to pretty print the JSON
            try:
                import json
                parsed = json.loads(content)
                print(json.dumps(parsed, indent=2))
            except:
                print(content)
            
            # Parse response
            evaluation = self._parse_evaluation_response(
                content, rule_id, rule_name, severity, relevant_sections
            )
            
            return evaluation
            
        except Exception as e:
            print(f"Error evaluating rule {rule_id}: {e}")
            return RuleEvaluation(
                rule_id=rule_id,
                rule_name=rule_name,
                status=ComplianceStatus.REQUIRES_REVIEW,
                confidence=0.0,
                rationale=f"Error during evaluation: {str(e)}",
                severity=severity
            )
    
    def _create_evaluation_prompt(self,
                                 rule_name: str,
                                 rule_text: str,
                                 context_text: str,
                                 exceptions: List[str]) -> Tuple[str, str]:
        """Create system message and user prompt for rule evaluation"""
        
        # Load prompt template from YAML
        prompt_template = load_prompt_template('rule_compliance_evaluation')
        
        # Format exceptions text if applicable
        exceptions_text = ""
        if exceptions:
            exceptions_text = "\nExceptions that may apply:\n" + "\n".join(f"- {e}" for e in exceptions)
        
        # Get system message from template
        system_message = prompt_template.get('system_message', '').strip()
        
        # Format user message from template
        user_prompt = prompt_template.get('user_message_template', '').format(
            rule_name=rule_name,
            rule_text=rule_text,
            exceptions_text=exceptions_text,
            context_text=context_text
        )
        
        return system_message, user_prompt
    
    def _parse_evaluation_response(self,
                                  response: str,
                                  rule_id: str,
                                  rule_name: str,
                                  severity: str,
                                  relevant_sections: List[Dict[str, Any]]) -> RuleEvaluation:
        """Parse LLM evaluation response"""
        
        try:
            result = json.loads(response)
        except json.JSONDecodeError:
            # Fallback parsing
            result = {
                'status': 'requires_review',
                'confidence': 0.5,
                'rationale': response[:500] if response else 'Unable to parse evaluation'
            }
        
        # Map status string to enum
        status_map = {
            'compliant': ComplianceStatus.COMPLIANT,
            'non_compliant': ComplianceStatus.NON_COMPLIANT,
            'partially_compliant': ComplianceStatus.PARTIALLY_COMPLIANT,
            'not_applicable': ComplianceStatus.NOT_APPLICABLE,
            'requires_review': ComplianceStatus.REQUIRES_REVIEW
        }
        
        status = status_map.get(
            result.get('status', 'requires_review'),
            ComplianceStatus.REQUIRES_REVIEW
        )
        
        # Create evaluation result
        evaluation = RuleEvaluation(
            rule_id=rule_id,
            rule_name=rule_name,
            status=status,
            confidence=float(result.get('confidence', 0.5)),
            rationale=result.get('rationale', ''),
            severity=severity,
            exceptions_applied=result.get('exceptions_applied', []),
            relevant_sections=[s['text'] for s in relevant_sections[:3]]
        )
        
        # Add evidence quotes as citations
        for quote in result.get('evidence_quotes', []):
            evaluation.citations.append({
                'quote': quote,
                'type': 'evidence'
            })
        
        # Add specific issues to rationale if non-compliant
        if status == ComplianceStatus.NON_COMPLIANT:
            issues = result.get('specific_issues', [])
            if issues:
                evaluation.rationale += "\n\nSpecific issues:\n" + "\n".join(f"• {i}" for i in issues)
        
        return evaluation
    
    def _display_rule_result(self, 
                           rule_name: str, 
                           evaluation: RuleEvaluation, 
                           status_symbol: str,
                           current_idx: int,
                           total_rules: int):
        """Display nicely formatted LLM analysis result for a rule"""
        
        # Create a formatted display with visual separator
        print(f"\n{'─' * 80}")
        print(f"📋 Rule {current_idx}/{total_rules}: {rule_name}")
        print(f"{'─' * 80}")
        
        # Status line with confidence
        status_line = f"{status_symbol} Status: {evaluation.status.value.upper()}"
        if evaluation.confidence > 0:
            confidence_pct = int(evaluation.confidence * 100)
            status_line += f" (Confidence: {confidence_pct}%)"
        print(status_line)
        
        # Severity indicator for non-compliant rules
        if evaluation.status == ComplianceStatus.NON_COMPLIANT:
            severity_symbols = {
                'critical': '🔴',
                'high': '🟠',
                'medium': '🟡',
                'low': '🟢'
            }
            severity_symbol = severity_symbols.get(evaluation.severity, '⚪')
            print(f"{severity_symbol} Severity: {evaluation.severity.upper()}")
        
        # Analysis rationale
        print("\n📝 Analysis:")
        # Format rationale with proper indentation
        rationale_lines = evaluation.rationale.split('\n')
        for line in rationale_lines:
            if line.strip():
                if line.startswith('•') or line.startswith('-'):
                    print(f"  {line}")
                else:
                    print(f"   {line}")
        
        # Display exceptions if applied
        if evaluation.exceptions_applied:
            print("\n⚖️ Exceptions Applied:")
            for exception in evaluation.exceptions_applied:
                print(f"   • {exception}")
        
        # Display evidence quotes if available
        if evaluation.citations:
            print("\n📌 Evidence from Document:")
            for i, citation in enumerate(evaluation.citations[:3], 1):  # Limit to 3 quotes
                quote = citation.get('quote', '')
                if quote:
                    # Truncate long quotes
                    if len(quote) > 200:
                        quote = quote[:197] + "..."
                    print(f"   {i}. \"{quote}\"")
        
        # Display relevant sections if available
        if evaluation.relevant_sections and evaluation.status != ComplianceStatus.NOT_APPLICABLE:
            print(f"\n📄 Relevant Document Sections Found: {len(evaluation.relevant_sections)}")
            # Show first section snippet
            if evaluation.relevant_sections:
                first_section = evaluation.relevant_sections[0]
                if len(first_section) > 150:
                    first_section = first_section[:147] + "..."
                print(f"   First match: \"{first_section}\"")
        
        # Report to UI with detailed message
        detailed_msg = f"Evaluated: {rule_name}\nStatus: {evaluation.status.value}\nConfidence: {evaluation.confidence:.0%}"
        if evaluation.status == ComplianceStatus.NON_COMPLIANT:
            detailed_msg += f"\nSeverity: {evaluation.severity}"
        
        self.report_progress(
            detailed_msg,
            progress=current_idx / total_rules,
            details={
                'rule_name': rule_name,
                'status': evaluation.status.value,
                'confidence': evaluation.confidence,
                'severity': evaluation.severity,
                'has_evidence': len(evaluation.citations) > 0,
                'exceptions_applied': len(evaluation.exceptions_applied) > 0
            }
        )
    
    def evaluate_all_rules(self,
                          rules: List[Dict[str, Any]],
                          document_text: str,
                          progress_callback: Optional[callable] = None) -> List[RuleEvaluation]:
        """Evaluate all rules against the document"""
        
        evaluations = []
        total_rules = len(rules)
        
        self.report_progress(f"Evaluating {total_rules} rules against document", progress=0.0)
        
        for idx, rule in enumerate(rules):
            rule_name = rule.get('name', rule.get('id', 'Unknown'))
            
            # Report subtask progress
            self.report_subtask(
                "Evaluating rules",
                idx + 1,
                total_rules,
                f"Processing: {rule_name}"
            )
            
            # Find relevant sections
            relevant_sections = self.find_relevant_sections(document_text, rule)
            
            # Evaluate rule
            evaluation = self.evaluate_single_rule(rule, document_text, relevant_sections)
            evaluations.append(evaluation)
            
            # Log result with progress
            status_symbol = {
                ComplianceStatus.COMPLIANT: "✅",
                ComplianceStatus.NON_COMPLIANT: "❌",
                ComplianceStatus.PARTIALLY_COMPLIANT: "⚠️",
                ComplianceStatus.NOT_APPLICABLE: "➖",
                ComplianceStatus.REQUIRES_REVIEW: "🔍"
            }.get(evaluation.status, "❓")
            
            # Display detailed analysis result
            self._display_rule_result(rule_name, evaluation, status_symbol, idx + 1, total_rules)
            
            self.report_progress(
                f"{status_symbol} {rule_name}: {evaluation.status.value}",
                progress=(idx + 1) / total_rules,
                details={
                    'rule': rule_name,
                    'status': evaluation.status.value,
                    'confidence': evaluation.confidence
                }
            )
        
        return evaluations
    
    def create_compliance_summary(self, evaluations: List[RuleEvaluation]) -> Dict[str, Any]:
        """Create a summary of compliance results"""
        
        total = len(evaluations)
        compliant = sum(1 for e in evaluations if e.status == ComplianceStatus.COMPLIANT)
        non_compliant = sum(1 for e in evaluations if e.status == ComplianceStatus.NON_COMPLIANT)
        partial = sum(1 for e in evaluations if e.status == ComplianceStatus.PARTIALLY_COMPLIANT)
        not_applicable = sum(1 for e in evaluations if e.status == ComplianceStatus.NOT_APPLICABLE)
        review_needed = sum(1 for e in evaluations if e.status == ComplianceStatus.REQUIRES_REVIEW)
        
        # Group by severity
        critical_issues = [e for e in evaluations 
                          if e.status == ComplianceStatus.NON_COMPLIANT 
                          and e.severity == 'critical']
        high_issues = [e for e in evaluations 
                      if e.status == ComplianceStatus.NON_COMPLIANT 
                      and e.severity == 'high']
        
        # Calculate overall compliance score
        weights = {
            ComplianceStatus.COMPLIANT: 1.0,
            ComplianceStatus.PARTIALLY_COMPLIANT: 0.5,
            ComplianceStatus.NON_COMPLIANT: 0.0,
            ComplianceStatus.NOT_APPLICABLE: None,  # Don't count
            ComplianceStatus.REQUIRES_REVIEW: 0.25
        }
        
        scored_evaluations = [e for e in evaluations 
                             if e.status != ComplianceStatus.NOT_APPLICABLE]
        
        if scored_evaluations:
            compliance_score = sum(
                weights.get(e.status, 0) * e.confidence 
                for e in scored_evaluations
            ) / len(scored_evaluations)
        else:
            compliance_score = 0.0
        
        return {
            'total_rules': total,
            'compliant': compliant,
            'non_compliant': non_compliant,
            'partially_compliant': partial,
            'not_applicable': not_applicable,
            'requires_review': review_needed,
            'compliance_score': compliance_score,
            'critical_issues': len(critical_issues),
            'high_priority_issues': len(high_issues),
            'critical_issue_details': [
                {
                    'rule_id': e.rule_id,
                    'rule_name': e.rule_name,
                    'rationale': e.rationale
                }
                for e in critical_issues
            ]
        }


def evaluate_document_compliance(state: Dict[str, Any]) -> Dict[str, Any]:
    """Main node function for rule compliance evaluation"""
    
    print("\n" + "="*60)
    print("📋 RULE COMPLIANCE EVALUATION")
    print("="*60)
    
    evaluator = RuleComplianceEvaluator()
    
    # Get inputs from state
    rules_path = state.get('rules_path')
    document_text = state.get('document_text', '')
    
    if not rules_path:
        print("⚠️ No rules file specified, skipping rule evaluation")
        return state
    
    try:
        # Load all rules
        rules = evaluator.load_rules(rules_path)
        print(f"📚 Loaded {len(rules)} rules from {os.path.basename(rules_path)}")
        
        # Evaluate all rules
        evaluations = evaluator.evaluate_all_rules(rules, document_text)
        
        # Create summary
        summary = evaluator.create_compliance_summary(evaluations)
        
        # Convert evaluations to dict format for state
        evaluation_dicts = []
        for eval in evaluations:
            evaluation_dicts.append({
                'rule_id': eval.rule_id,
                'rule_name': eval.rule_name,
                'status': eval.status.value,
                'confidence': eval.confidence,
                'rationale': eval.rationale,
                'severity': eval.severity,
                'exceptions_applied': eval.exceptions_applied,
                'relevant_sections': eval.relevant_sections,
                'citations': eval.citations
            })
        
        # Update state
        state['rule_compliance_results'] = evaluation_dicts
        state['rule_compliance_summary'] = summary
        
        # Print summary
        print("\n📊 Compliance Summary:")
        print(f"  • Total Rules: {summary['total_rules']}")
        print(f"  • Compliant: {summary['compliant']} ✅")
        print(f"  • Non-Compliant: {summary['non_compliant']} ❌")
        print(f"  • Partially Compliant: {summary['partially_compliant']} ⚠️")
        print(f"  • Not Applicable: {summary['not_applicable']} ➖")
        print(f"  • Requires Review: {summary['requires_review']} 🔍")
        print(f"  • Overall Compliance Score: {summary['compliance_score']:.1%}")
        
        if summary['critical_issues'] > 0:
            print(f"\n⚠️ CRITICAL ISSUES FOUND: {summary['critical_issues']}")
            for issue in summary['critical_issue_details'][:3]:
                print(f"  • {issue['rule_name']}: {issue['rationale'][:100]}...")
        
        print("\n✅ Rule compliance evaluation complete")
        
        # Save rule evaluation results for inspection
        try:
            run_id = state.get('run_id') or state.get('processing_start_time', '').replace('-', '').replace('T', '_').replace(':', '')[:15]
            save_rule_evaluation_results(
                results,
                run_id=run_id
            )
        except Exception as save_error:
            print(f"  ⚠️ Could not save rule evaluation results: {save_error}")
        
    except Exception as e:
        print(f"❌ Error in rule compliance evaluation: {e}")
        state['processing_errors'] = state.get('processing_errors', [])
        state['processing_errors'].append(f"Rule evaluation error: {str(e)}")
    
    return state