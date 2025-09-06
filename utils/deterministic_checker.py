"""
Deterministic Rule Checker
Performs pattern-based rule checking before falling back to LLM
"""

import re
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
import logging

from utils.rule_manager import Rule

logger = logging.getLogger(__name__)


@dataclass
class PatternMatch:
    """Result of a pattern match"""
    pattern: str
    text: str
    start: int
    end: int
    page: Optional[int] = None
    confidence: float = 1.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "pattern": self.pattern,
            "matched_text": self.text[:100] + "..." if len(self.text) > 100 else self.text,
            "position": {"start": self.start, "end": self.end},
            "page": self.page,
            "confidence": self.confidence
        }


@dataclass
class DeterministicResult:
    """Result of deterministic rule checking"""
    rule_id: str
    is_conclusive: bool
    status: Optional[str] = None  # compliant, non_compliant, not_applicable, unknown
    confidence: float = 0.0
    keyword_matches: List[PatternMatch] = field(default_factory=list)
    regex_matches: List[PatternMatch] = field(default_factory=list)
    proximity_matches: List[Dict[str, Any]] = field(default_factory=list)
    section_matches: List[str] = field(default_factory=list)
    rationale: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "is_conclusive": self.is_conclusive,
            "status": self.status,
            "confidence": self.confidence,
            "rationale": self.rationale,
            "evidence": {
                "keyword_matches": len(self.keyword_matches),
                "regex_matches": len(self.regex_matches),
                "proximity_matches": len(self.proximity_matches),
                "section_matches": self.section_matches
            }
        }


class DeterministicRuleChecker:
    """Performs deterministic pattern-based rule checking"""
    
    def __init__(self, confidence_threshold: float = 0.7):
        """
        Initialize deterministic checker
        
        Args:
            confidence_threshold: Minimum confidence for conclusive result
        """
        self.confidence_threshold = confidence_threshold
        self.stats = {
            "total_checks": 0,
            "conclusive_results": 0,
            "fallback_to_llm": 0
        }
    
    def check_rule(
        self,
        rule: Rule,
        document_text: str,
        sentences: Optional[List[str]] = None,
        page_map: Optional[Dict[int, int]] = None
    ) -> DeterministicResult:
        """
        Check rule using deterministic patterns
        
        Args:
            rule: Rule to check
            document_text: Full document text
            sentences: Optional list of sentences
            page_map: Optional mapping of character position to page
            
        Returns:
            Deterministic result
        """
        self.stats["total_checks"] += 1
        
        result = DeterministicResult(
            rule_id=rule.rule_id,
            is_conclusive=False
        )
        
        # Check required keywords
        keyword_result = self._check_keywords(
            document_text,
            rule.deterministic_checks.required_keywords,
            rule.deterministic_checks.forbidden_keywords,
            page_map
        )
        result.keyword_matches = keyword_result["matches"]
        
        # Check regex patterns
        regex_result = self._check_regex_patterns(
            document_text,
            rule.deterministic_checks.regex_patterns,
            page_map
        )
        result.regex_matches = regex_result["matches"]
        
        # Check proximity rules
        if rule.deterministic_checks.proximity_rules:
            proximity_result = self._check_proximity_rules(
                document_text,
                rule.deterministic_checks.proximity_rules,
                page_map
            )
            result.proximity_matches = proximity_result["matches"]
        
        # Check section hints
        if rule.deterministic_checks.section_hints and sentences:
            section_result = self._check_section_hints(
                sentences,
                rule.deterministic_checks.section_hints
            )
            result.section_matches = section_result["matches"]
        
        # Determine if result is conclusive
        result = self._evaluate_conclusiveness(result, rule)
        
        if result.is_conclusive:
            self.stats["conclusive_results"] += 1
        else:
            self.stats["fallback_to_llm"] += 1
        
        return result
    
    def _check_keywords(
        self,
        text: str,
        required: List[str],
        forbidden: List[str],
        page_map: Optional[Dict[int, int]] = None
    ) -> Dict[str, Any]:
        """Check for required and forbidden keywords"""
        text_lower = text.lower()
        matches = []
        
        # Check required keywords
        required_found = set()
        for keyword in required:
            keyword_lower = keyword.lower()
            
            # Find all occurrences
            start = 0
            while True:
                pos = text_lower.find(keyword_lower, start)
                if pos == -1:
                    break
                
                # Extract surrounding context
                context_start = max(0, pos - 50)
                context_end = min(len(text), pos + len(keyword) + 50)
                context = text[context_start:context_end]
                
                # Get page number if available
                page = page_map.get(pos) if page_map else None
                
                matches.append(PatternMatch(
                    pattern=f"keyword:{keyword}",
                    text=context,
                    start=pos,
                    end=pos + len(keyword),
                    page=page,
                    confidence=1.0
                ))
                
                required_found.add(keyword)
                start = pos + 1
        
        # Check forbidden keywords
        forbidden_found = set()
        for keyword in forbidden:
            keyword_lower = keyword.lower()
            if keyword_lower in text_lower:
                forbidden_found.add(keyword)
                
                # Find first occurrence for evidence
                pos = text_lower.find(keyword_lower)
                context_start = max(0, pos - 50)
                context_end = min(len(text), pos + len(keyword) + 50)
                context = text[context_start:context_end]
                
                page = page_map.get(pos) if page_map else None
                
                matches.append(PatternMatch(
                    pattern=f"forbidden:{keyword}",
                    text=context,
                    start=pos,
                    end=pos + len(keyword),
                    page=page,
                    confidence=-1.0  # Negative confidence for forbidden
                ))
        
        return {
            "matches": matches,
            "required_found": required_found,
            "forbidden_found": forbidden_found,
            "all_required": len(required_found) == len(required) if required else True,
            "no_forbidden": len(forbidden_found) == 0
        }
    
    def _check_regex_patterns(
        self,
        text: str,
        patterns: List[str],
        page_map: Optional[Dict[int, int]] = None
    ) -> Dict[str, Any]:
        """Check regex patterns"""
        matches = []
        patterns_found = set()
        
        for pattern in patterns:
            try:
                regex = re.compile(pattern, re.IGNORECASE | re.MULTILINE)
                
                for match in regex.finditer(text):
                    # Extract matched text and context
                    match.group(0)
                    start = match.start()
                    end = match.end()
                    
                    context_start = max(0, start - 50)
                    context_end = min(len(text), end + 50)
                    context = text[context_start:context_end]
                    
                    page = page_map.get(start) if page_map else None
                    
                    matches.append(PatternMatch(
                        pattern=f"regex:{pattern}",
                        text=context,
                        start=start,
                        end=end,
                        page=page,
                        confidence=0.9  # Slightly lower confidence for regex
                    ))
                    
                    patterns_found.add(pattern)
                    
            except re.error as e:
                logger.error(f"Regex error for pattern {pattern}: {str(e)}")
        
        return {
            "matches": matches,
            "patterns_found": patterns_found,
            "match_count": len(matches)
        }
    
    def _check_proximity_rules(
        self,
        text: str,
        proximity_rules: List[Dict[str, Any]],
        page_map: Optional[Dict[int, int]] = None
    ) -> Dict[str, Any]:
        """Check proximity-based rules"""
        matches = []
        text_lower = text.lower()
        
        for rule in proximity_rules:
            terms = [t.lower() for t in rule["terms"]]
            max_distance = rule["max_distance"]
            
            # Find all occurrences of first term
            term1 = terms[0]
            term2 = terms[1] if len(terms) > 1 else None
            
            if not term2:
                continue
            
            # Find positions of both terms
            positions1 = []
            start = 0
            while True:
                pos = text_lower.find(term1, start)
                if pos == -1:
                    break
                positions1.append(pos)
                start = pos + 1
            
            positions2 = []
            start = 0
            while True:
                pos = text_lower.find(term2, start)
                if pos == -1:
                    break
                positions2.append(pos)
                start = pos + 1
            
            # Check proximity
            for pos1 in positions1:
                for pos2 in positions2:
                    # Calculate word distance (approximate)
                    char_distance = abs(pos2 - pos1)
                    word_distance = char_distance // 5  # Rough estimate
                    
                    if word_distance <= max_distance:
                        # Found proximity match
                        start = min(pos1, pos2)
                        end = max(pos1 + len(term1), pos2 + len(term2))
                        
                        context_start = max(0, start - 30)
                        context_end = min(len(text), end + 30)
                        context = text[context_start:context_end]
                        
                        page = page_map.get(start) if page_map else None
                        
                        matches.append({
                            "terms": rule["terms"],
                            "distance": word_distance,
                            "max_distance": max_distance,
                            "context": context,
                            "page": page
                        })
        
        return {
            "matches": matches,
            "match_count": len(matches)
        }
    
    def _check_section_hints(
        self,
        sentences: List[str],
        section_hints: List[str]
    ) -> Dict[str, Any]:
        """Check if relevant sections exist"""
        matches = []
        
        # Look for section headers
        for sentence in sentences[:50]:  # Check first 50 sentences for headers
            sentence_lower = sentence.lower()
            
            for hint in section_hints:
                hint_lower = hint.lower()
                if hint_lower in sentence_lower:
                    # Check if it looks like a header (short, possibly numbered)
                    if len(sentence) < 100:
                        matches.append(hint)
                        break
        
        return {
            "matches": matches,
            "found_sections": len(matches) > 0
        }
    
    def _evaluate_conclusiveness(
        self,
        result: DeterministicResult,
        rule: Rule
    ) -> DeterministicResult:
        """Evaluate if deterministic checks are conclusive"""
        
        # Calculate confidence based on matches
        confidence_factors = []
        
        # Keyword matches
        if result.keyword_matches:
            keyword_confidence = len([m for m in result.keyword_matches if m.confidence > 0])
            keyword_confidence /= max(len(rule.deterministic_checks.required_keywords), 1)
            confidence_factors.append(keyword_confidence)
            
            # Check for forbidden keywords
            forbidden_count = len([m for m in result.keyword_matches if m.confidence < 0])
            if forbidden_count > 0:
                confidence_factors.append(0.0)  # Forbidden keywords found
        
        # Regex matches
        if result.regex_matches:
            regex_confidence = min(len(result.regex_matches) / 2.0, 1.0)  # Cap at 2 matches
            confidence_factors.append(regex_confidence * 0.9)  # Slightly lower weight
        
        # Proximity matches
        if result.proximity_matches:
            proximity_confidence = min(len(result.proximity_matches) / 2.0, 1.0)
            confidence_factors.append(proximity_confidence * 0.8)
        
        # Section matches
        if result.section_matches:
            confidence_factors.append(0.5)  # Section hints are supporting evidence
        
        # Calculate overall confidence
        if confidence_factors:
            result.confidence = sum(confidence_factors) / len(confidence_factors)
        else:
            result.confidence = 0.0
        
        # Determine if conclusive
        if result.confidence >= self.confidence_threshold:
            result.is_conclusive = True
            
            # Determine status based on matches
            if result.keyword_matches or result.regex_matches:
                # Check if we have strong positive evidence
                positive_matches = len([m for m in result.keyword_matches if m.confidence > 0])
                positive_matches += len(result.regex_matches)
                
                if positive_matches >= 2:
                    result.status = "compliant"
                    result.rationale = f"Found {positive_matches} positive pattern matches indicating compliance"
                else:
                    result.status = "non_compliant"
                    result.rationale = "Insufficient evidence of compliance based on pattern matching"
            else:
                result.status = "non_compliant"
                result.rationale = "No required patterns found in document"
        
        # Check for definitive non-compliance
        elif any(m.confidence < 0 for m in result.keyword_matches):
            result.is_conclusive = True
            result.status = "non_compliant"
            result.confidence = 0.9
            result.rationale = "Found forbidden keywords indicating non-compliance"
        
        return result
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get checker statistics"""
        total = self.stats["total_checks"]
        if total == 0:
            return self.stats
        
        return {
            **self.stats,
            "conclusive_rate": self.stats["conclusive_results"] / total,
            "llm_fallback_rate": self.stats["fallback_to_llm"] / total
        }
    
    def reset_statistics(self):
        """Reset statistics"""
        self.stats = {
            "total_checks": 0,
            "conclusive_results": 0,
            "fallback_to_llm": 0
        }


# Global deterministic checker instance
deterministic_checker = DeterministicRuleChecker()


def check_rule_deterministic(
    rule: Rule,
    document_text: str,
    sentences: Optional[List[str]] = None,
    page_map: Optional[Dict[int, int]] = None
) -> DeterministicResult:
    """
    Convenience function to check rule deterministically
    
    Args:
        rule: Rule to check
        document_text: Document text
        sentences: Optional sentences list
        page_map: Optional page mapping
        
    Returns:
        Deterministic result
    """
    return deterministic_checker.check_rule(rule, document_text, sentences, page_map)