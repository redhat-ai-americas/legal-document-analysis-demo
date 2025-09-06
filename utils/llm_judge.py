"""
LLM Judge for Rule Compliance
Evaluates rules using LLM with strict schema enforcement
"""

import json
import time
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
import logging

from utils.rule_manager import Rule
from utils.citation_manager import Citation, citation_manager
from utils.schema_enforcer import SchemaEnforcer
from utils.model_client import ModelClient
from utils.model_factory import get_model_client

logger = logging.getLogger(__name__)


# JSON schema for LLM response
LLM_RESPONSE_SCHEMA = {
    "type": "object",
    "required": ["rule_id", "status", "rationale", "citations", "attribution"],
    "properties": {
        "rule_id": {
            "type": "string",
            "pattern": "^[A-Z]+-[0-9]{3}$"
        },
        "status": {
            "type": "string",
            "enum": ["compliant", "non_compliant", "not_applicable", "unknown"]
        },
        "rationale": {
            "type": "string",
            "minLength": 20
        },
        "violating_spans": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["text", "page"],
                "properties": {
                    "text": {"type": "string"},
                    "page": {"type": "integer", "minimum": 1},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1}
                }
            }
        },
        "citations": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["quote", "anchor"],
                "properties": {
                    "quote": {"type": "string", "minLength": 10},
                    "anchor": {
                        "type": "string",
                        "pattern": "^\\[\\[page=\\d+\\]\\]$"
                    }
                }
            }
        },
        "attribution": {
            "type": "object",
            "required": ["method", "model", "confidence"],
            "properties": {
                "method": {"type": "string"},
                "model": {"type": "string"},
                "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                "tokens_used": {"type": "integer"}
            }
        }
    }
}


@dataclass
class LLMJudgment:
    """Result of LLM rule evaluation"""
    rule_id: str
    status: str  # compliant, non_compliant, not_applicable, unknown
    rationale: str
    citations: List[Citation] = field(default_factory=list)
    violating_spans: List[Dict[str, Any]] = field(default_factory=list)
    confidence: float = 0.0
    attribution: Dict[str, Any] = field(default_factory=dict)
    raw_response: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "rule_id": self.rule_id,
            "status": self.status,
            "rationale": self.rationale,
            "citations": [c.to_dict() for c in self.citations],
            "violating_spans": self.violating_spans,
            "attribution": self.attribution
        }


class LLMJudge:
    """Evaluates rules using LLM"""
    
    def __init__(
        self,
        model_client: Optional[ModelClient] = None,
        max_retries: int = 3,
        require_citations: bool = True
    ):
        """
        Initialize LLM judge
        
        Args:
            model_client: Model client to use
            max_retries: Maximum retries for schema compliance
            require_citations: Whether citations are required
        """
        self.model_client = model_client or get_model_client()
        self.max_retries = max_retries
        self.require_citations = require_citations
        self.schema_enforcer = SchemaEnforcer()
        
        self.stats = {
            "total_evaluations": 0,
            "successful_evaluations": 0,
            "schema_failures": 0,
            "retry_count": 0
        }
    
    def evaluate_rule(
        self,
        rule: Rule,
        document_text: str,
        relevant_sentences: List[str] = None,
        page_map: Optional[Dict[int, int]] = None
    ) -> LLMJudgment:
        """
        Evaluate rule compliance using LLM
        
        Args:
            rule: Rule to evaluate
            document_text: Document text
            relevant_sentences: Pre-filtered relevant sentences
            page_map: Character to page mapping
            
        Returns:
            LLM judgment
        """
        self.stats["total_evaluations"] += 1
        
        # Prepare context
        if relevant_sentences:
            context = "\n".join(relevant_sentences[:20])  # Limit context
        else:
            # Use first 5000 characters as context
            context = document_text[:5000]
        
        # Build prompt
        prompt = self._build_prompt(rule, context)
        
        # Try to get valid response with retries
        for attempt in range(self.max_retries):
            try:
                # Call LLM
                start_time = time.time()
                response = self.model_client.generate(
                    prompt,
                    temperature=0.1,  # Low temperature for consistency
                    max_tokens=1000
                )
                elapsed = time.time() - start_time
                
                # Extract JSON from response
                json_data = self.schema_enforcer.extract_json(response)
                
                if not json_data:
                    if attempt < self.max_retries - 1:
                        self.stats["retry_count"] += 1
                        # Add schema hint to prompt
                        prompt = self._add_schema_hint(prompt, response)
                        continue
                    else:
                        # Final attempt failed
                        return self._create_fallback_judgment(rule, "Failed to extract valid JSON")
                
                # Validate against schema
                is_valid, errors = self.schema_enforcer.validate_json(
                    json_data,
                    LLM_RESPONSE_SCHEMA
                )
                
                if not is_valid:
                    if attempt < self.max_retries - 1:
                        self.stats["retry_count"] += 1
                        # Add error feedback to prompt
                        prompt = self._add_error_feedback(prompt, errors)
                        continue
                    else:
                        self.stats["schema_failures"] += 1
                        return self._create_fallback_judgment(rule, f"Schema validation failed: {errors}")
                
                # Parse valid response
                judgment = self._parse_response(json_data, rule, document_text, page_map)
                judgment.raw_response = response
                judgment.attribution["time_seconds"] = elapsed
                judgment.attribution["attempts"] = attempt + 1
                
                self.stats["successful_evaluations"] += 1
                return judgment
                
            except Exception as e:
                logger.error(f"LLM evaluation error: {str(e)}")
                if attempt == self.max_retries - 1:
                    return self._create_fallback_judgment(rule, str(e))
        
        # Should not reach here
        return self._create_fallback_judgment(rule, "Maximum retries exceeded")
    
    def _build_prompt(self, rule: Rule, context: str) -> str:
        """Build evaluation prompt"""
        
        # Base prompt
        prompt = f"""You are a legal compliance expert evaluating a contract against a specific rule.

RULE TO EVALUATE:
ID: {rule.rule_id}
Category: {rule.category}
Description: {rule.description}
Priority: {rule.priority}

COMPLIANCE CRITERIA:
- Compliant: {rule.compliance_levels.compliant}
- Non-compliant: {rule.compliance_levels.non_compliant}
- Not applicable: {rule.compliance_levels.not_applicable}
- Unknown: {rule.compliance_levels.unknown}

CONTRACT TEXT TO ANALYZE:
{context}

EVALUATION INSTRUCTIONS:
{rule.llm_prompt or 'Evaluate if the contract text complies with the rule.'}

IMPORTANT REQUIREMENTS:
1. You MUST provide specific quotes from the contract text as evidence
2. Each quote must include a page anchor in format [[page=N]]
3. Your response must be valid JSON matching this schema:
{json.dumps(LLM_RESPONSE_SCHEMA, indent=2)}

"""
        
        # Add examples if available
        if rule.llm_examples:
            prompt += "\nEXAMPLES:\n"
            for example in rule.llm_examples[:2]:  # Limit to 2 examples
                prompt += f"""
Input: {example['text']}
Status: {example['status']}
Rationale: {example['rationale']}
"""
        
        prompt += """
RESPONSE (valid JSON only):
"""
        
        return prompt
    
    def _add_schema_hint(self, prompt: str, failed_response: str) -> str:
        """Add schema hint after failed attempt"""
        hint = f"""

PREVIOUS RESPONSE WAS INVALID. Please provide ONLY valid JSON matching this exact structure:
{{
    "rule_id": "{self.current_rule_id if hasattr(self, 'current_rule_id') else 'RULE-001'}",
    "status": "compliant|non_compliant|not_applicable|unknown",
    "rationale": "Clear explanation of the evaluation",
    "citations": [
        {{
            "quote": "Exact quote from the contract",
            "anchor": "[[page=1]]"
        }}
    ],
    "attribution": {{
        "method": "llm_judgment",
        "model": "granite-3.3",
        "confidence": 0.85
    }}
}}

RESPONSE (valid JSON only):
"""
        return prompt + hint
    
    def _add_error_feedback(self, prompt: str, errors: List[str]) -> str:
        """Add error feedback to prompt"""
        feedback = f"""

SCHEMA VALIDATION ERRORS:
{chr(10).join(f"- {error}" for error in errors)}

Please fix these errors and provide valid JSON.

RESPONSE (valid JSON only):
"""
        return prompt + feedback
    
    def _parse_response(
        self,
        json_data: Dict[str, Any],
        rule: Rule,
        document_text: str,
        page_map: Optional[Dict[int, int]]
    ) -> LLMJudgment:
        """Parse LLM response into judgment"""
        
        # Create judgment
        judgment = LLMJudgment(
            rule_id=json_data["rule_id"],
            status=json_data["status"],
            rationale=json_data["rationale"],
            confidence=json_data["attribution"]["confidence"],
            attribution=json_data["attribution"]
        )
        
        # Parse citations
        for citation_data in json_data.get("citations", []):
            # Extract page from anchor
            page_match = citation_manager.page_anchor_pattern.search(citation_data["anchor"])
            if page_match:
                page = int(page_match.group(1))
            else:
                page = 1
            
            # Create citation
            citation = citation_manager.create_citation(
                citation_data["quote"],
                document_text,
                page_map=page_map
            )
            
            if citation:
                citation.page = page  # Use LLM-provided page
                judgment.citations.append(citation)
        
        # Parse violating spans
        judgment.violating_spans = json_data.get("violating_spans", [])
        
        return judgment
    
    def _create_fallback_judgment(self, rule: Rule, error: str) -> LLMJudgment:
        """Create fallback judgment when LLM fails"""
        return LLMJudgment(
            rule_id=rule.rule_id,
            status="unknown",
            rationale=f"Unable to evaluate rule due to: {error}",
            confidence=0.0,
            attribution={
                "method": "fallback",
                "model": "none",
                "confidence": 0.0,
                "error": error
            }
        )
    
    def batch_evaluate(
        self,
        rules: List[Rule],
        document_text: str,
        relevant_sentences: Optional[Dict[str, List[str]]] = None,
        page_map: Optional[Dict[int, int]] = None
    ) -> List[LLMJudgment]:
        """
        Evaluate multiple rules
        
        Args:
            rules: Rules to evaluate
            document_text: Document text
            relevant_sentences: Dict of rule_id to relevant sentences
            page_map: Page mapping
            
        Returns:
            List of judgments
        """
        judgments = []
        
        for rule in rules:
            # Get relevant sentences for this rule if provided
            rule_sentences = None
            if relevant_sentences and rule.rule_id in relevant_sentences:
                rule_sentences = relevant_sentences[rule.rule_id]
            
            # Evaluate rule
            judgment = self.evaluate_rule(
                rule,
                document_text,
                rule_sentences,
                page_map
            )
            
            judgments.append(judgment)
        
        return judgments
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get evaluation statistics"""
        total = self.stats["total_evaluations"]
        if total == 0:
            return self.stats
        
        return {
            **self.stats,
            "success_rate": self.stats["successful_evaluations"] / total,
            "schema_failure_rate": self.stats["schema_failures"] / total,
            "avg_retries": self.stats["retry_count"] / total
        }


# Global LLM judge instance
llm_judge = LLMJudge()


def evaluate_rule_with_llm(
    rule: Rule,
    document_text: str,
    relevant_sentences: List[str] = None,
    page_map: Optional[Dict[int, int]] = None
) -> LLMJudgment:
    """
    Convenience function to evaluate rule with LLM
    
    Args:
        rule: Rule to evaluate
        document_text: Document text
        relevant_sentences: Relevant sentences
        page_map: Page mapping
        
    Returns:
        LLM judgment
    """
    return llm_judge.evaluate_rule(rule, document_text, relevant_sentences, page_map)