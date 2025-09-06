"""
Rule Manager
Handles loading, parsing, and validation of JSON-based compliance rules
"""

import json
import re
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from jsonschema import validate, ValidationError
import logging

logger = logging.getLogger(__name__)


@dataclass
class DeterministicChecks:
    """Deterministic pattern checks for a rule"""
    required_keywords: List[str] = field(default_factory=list)
    forbidden_keywords: List[str] = field(default_factory=list)
    regex_patterns: List[str] = field(default_factory=list)
    proximity_rules: List[Dict[str, Any]] = field(default_factory=list)
    section_hints: List[str] = field(default_factory=list)


@dataclass
class EvidenceRequirements:
    """Evidence requirements for rule compliance"""
    min_citations: int = 1
    require_page_anchors: bool = True
    max_citation_distance: int = 500
    require_exact_quotes: bool = True


@dataclass
class ComplianceLevels:
    """Descriptions of compliance levels"""
    compliant: str
    non_compliant: str
    not_applicable: str
    unknown: str


@dataclass
class Rule:
    """Compliance rule definition"""
    rule_id: str
    category: str
    description: str
    priority: str
    deterministic_checks: DeterministicChecks
    evidence_requirements: EvidenceRequirements
    compliance_levels: ComplianceLevels
    llm_prompt: Optional[str] = None
    llm_examples: List[Dict[str, Any]] = field(default_factory=list)
    risk_level: Optional[str] = None
    remediation_guidance: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert rule to dictionary"""
        return {
            "rule_id": self.rule_id,
            "category": self.category,
            "description": self.description,
            "priority": self.priority,
            "risk_level": self.risk_level,
            "enabled": self.enabled,
            "deterministic_checks": {
                "required_keywords": self.deterministic_checks.required_keywords,
                "forbidden_keywords": self.deterministic_checks.forbidden_keywords,
                "regex_patterns": self.deterministic_checks.regex_patterns,
                "proximity_rules": self.deterministic_checks.proximity_rules,
                "section_hints": self.deterministic_checks.section_hints
            },
            "evidence_requirements": {
                "min_citations": self.evidence_requirements.min_citations,
                "require_page_anchors": self.evidence_requirements.require_page_anchors,
                "max_citation_distance": self.evidence_requirements.max_citation_distance,
                "require_exact_quotes": self.evidence_requirements.require_exact_quotes
            }
        }


class RuleManager:
    """Manages compliance rules"""
    
    def __init__(self, schema_path: Optional[str] = None):
        """
        Initialize rule manager
        
        Args:
            schema_path: Path to JSON schema for validation
        """
        self.rules: Dict[str, Rule] = {}
        self.categories: Dict[str, List[str]] = {}
        self.priority_map: Dict[str, List[str]] = {
            "critical": [],
            "high": [],
            "medium": [],
            "low": []
        }
        
        # Load schema
        if schema_path:
            self.schema = self._load_schema(schema_path)
        else:
            # Use default schema path
            default_path = Path(__file__).parent.parent / "config" / "rules_schema.json"
            if default_path.exists():
                self.schema = self._load_schema(str(default_path))
            else:
                self.schema = None
                logger.warning("No rules schema found for validation")
    
    def _load_schema(self, schema_path: str) -> Dict[str, Any]:
        """Load JSON schema"""
        try:
            with open(schema_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load schema: {str(e)}")
            return None
    
    def load_rules(self, rules_path: str) -> List[Rule]:
        """
        Load rules from JSON file
        
        Args:
            rules_path: Path to rules JSON file
            
        Returns:
            List of loaded rules
        """
        try:
            with open(rules_path, 'r') as f:
                rules_data = json.load(f)
            
            # Handle both single rule and list of rules
            if isinstance(rules_data, dict):
                rules_data = [rules_data]
            
            loaded_rules = []
            for rule_data in rules_data:
                # Validate against schema if available
                if self.schema:
                    try:
                        validate(instance=rule_data, schema=self.schema)
                    except ValidationError as e:
                        logger.error(f"Rule {rule_data.get('rule_id', 'unknown')} validation failed: {str(e)}")
                        continue
                
                # Parse rule
                rule = self._parse_rule(rule_data)
                if rule and rule.enabled:
                    self.add_rule(rule)
                    loaded_rules.append(rule)
            
            logger.info(f"Loaded {len(loaded_rules)} rules from {rules_path}")
            return loaded_rules
            
        except Exception as e:
            logger.error(f"Failed to load rules from {rules_path}: {str(e)}")
            return []
    
    def _parse_rule(self, rule_data: Dict[str, Any]) -> Optional[Rule]:
        """Parse rule from dictionary"""
        try:
            # Parse deterministic checks
            det_checks = rule_data.get("deterministic_checks", {})
            deterministic = DeterministicChecks(
                required_keywords=det_checks.get("required_keywords", []),
                forbidden_keywords=det_checks.get("forbidden_keywords", []),
                regex_patterns=det_checks.get("regex_patterns", []),
                proximity_rules=det_checks.get("proximity_rules", []),
                section_hints=det_checks.get("section_hints", [])
            )
            
            # Parse evidence requirements
            ev_reqs = rule_data.get("evidence_requirements", {})
            evidence = EvidenceRequirements(
                min_citations=ev_reqs.get("min_citations", 1),
                require_page_anchors=ev_reqs.get("require_page_anchors", True),
                max_citation_distance=ev_reqs.get("max_citation_distance", 500),
                require_exact_quotes=ev_reqs.get("require_exact_quotes", True)
            )
            
            # Parse compliance levels
            comp_levels = rule_data.get("compliance_levels", {})
            compliance = ComplianceLevels(
                compliant=comp_levels.get("compliant", ""),
                non_compliant=comp_levels.get("non_compliant", ""),
                not_applicable=comp_levels.get("not_applicable", ""),
                unknown=comp_levels.get("unknown", "")
            )
            
            # Create rule
            rule = Rule(
                rule_id=rule_data["rule_id"],
                category=rule_data["category"],
                description=rule_data["description"],
                priority=rule_data["priority"],
                deterministic_checks=deterministic,
                evidence_requirements=evidence,
                compliance_levels=compliance,
                llm_prompt=rule_data.get("llm_prompt"),
                llm_examples=rule_data.get("llm_examples", []),
                risk_level=rule_data.get("risk_level"),
                remediation_guidance=rule_data.get("remediation_guidance"),
                metadata=rule_data.get("metadata", {}),
                enabled=rule_data.get("enabled", True)
            )
            
            # Compile regex patterns
            for pattern in rule.deterministic_checks.regex_patterns:
                try:
                    re.compile(pattern)
                except re.error as e:
                    logger.error(f"Invalid regex in rule {rule.rule_id}: {pattern} - {str(e)}")
                    rule.deterministic_checks.regex_patterns.remove(pattern)
            
            return rule
            
        except Exception as e:
            logger.error(f"Failed to parse rule: {str(e)}")
            return None
    
    def add_rule(self, rule: Rule):
        """Add rule to manager"""
        self.rules[rule.rule_id] = rule
        
        # Update category index
        if rule.category not in self.categories:
            self.categories[rule.category] = []
        self.categories[rule.category].append(rule.rule_id)
        
        # Update priority index
        if rule.priority in self.priority_map:
            self.priority_map[rule.priority].append(rule.rule_id)
    
    def get_rule(self, rule_id: str) -> Optional[Rule]:
        """Get rule by ID"""
        return self.rules.get(rule_id)
    
    def get_rules_by_category(self, category: str) -> List[Rule]:
        """Get all rules in a category"""
        rule_ids = self.categories.get(category, [])
        return [self.rules[rid] for rid in rule_ids if rid in self.rules]
    
    def get_rules_by_priority(self, priority: str) -> List[Rule]:
        """Get all rules with a specific priority"""
        rule_ids = self.priority_map.get(priority, [])
        return [self.rules[rid] for rid in rule_ids if rid in self.rules]
    
    def get_active_rules(self) -> List[Rule]:
        """Get all enabled rules"""
        return [rule for rule in self.rules.values() if rule.enabled]
    
    def get_rules_for_document(self, document_type: str) -> List[Rule]:
        """
        Get relevant rules for a document type
        
        Args:
            document_type: Type of document being analyzed
            
        Returns:
            List of applicable rules
        """
        # Filter rules based on document type
        applicable_rules = []
        
        for rule in self.get_active_rules():
            # Check if rule applies to document type
            rule.metadata.get("tags", [])
            
            # Basic heuristic - can be enhanced
            if document_type.lower() in ["nda", "non-disclosure"]:
                if rule.category in ["confidentiality"]:
                    applicable_rules.append(rule)
            elif document_type.lower() in ["service", "services", "sow"]:
                if rule.category in ["payment", "termination", "liability", "performance"]:
                    applicable_rules.append(rule)
            else:
                # Default: include most rules
                if rule.category not in ["not_applicable_categories"]:
                    applicable_rules.append(rule)
        
        # Sort by priority
        priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        applicable_rules.sort(key=lambda r: priority_order.get(r.priority, 4))
        
        return applicable_rules
    
    def validate_rule(self, rule_data: Dict[str, Any]) -> bool:
        """
        Validate rule against schema
        
        Args:
            rule_data: Rule dictionary to validate
            
        Returns:
            True if valid, False otherwise
        """
        if not self.schema:
            logger.warning("No schema available for validation")
            return True
        
        try:
            validate(instance=rule_data, schema=self.schema)
            return True
        except ValidationError as e:
            logger.error(f"Rule validation failed: {str(e)}")
            return False
    
    def export_rules(self, output_path: str, category: Optional[str] = None):
        """
        Export rules to JSON file
        
        Args:
            output_path: Path to output file
            category: Optional category filter
        """
        if category:
            rules_to_export = self.get_rules_by_category(category)
        else:
            rules_to_export = list(self.rules.values())
        
        rules_data = []
        for rule in rules_to_export:
            rule_dict = rule.to_dict()
            # Add full rule data
            rule_dict["llm_prompt"] = rule.llm_prompt
            rule_dict["llm_examples"] = rule.llm_examples
            rule_dict["compliance_levels"] = {
                "compliant": rule.compliance_levels.compliant,
                "non_compliant": rule.compliance_levels.non_compliant,
                "not_applicable": rule.compliance_levels.not_applicable,
                "unknown": rule.compliance_levels.unknown
            }
            rule_dict["remediation_guidance"] = rule.remediation_guidance
            rule_dict["metadata"] = rule.metadata
            rules_data.append(rule_dict)
        
        try:
            with open(output_path, 'w') as f:
                json.dump(rules_data, f, indent=2)
            logger.info(f"Exported {len(rules_data)} rules to {output_path}")
        except Exception as e:
            logger.error(f"Failed to export rules: {str(e)}")
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get rule statistics"""
        stats = {
            "total_rules": len(self.rules),
            "enabled_rules": len(self.get_active_rules()),
            "categories": {
                cat: len(rules) for cat, rules in self.categories.items()
            },
            "priorities": {
                pri: len(rules) for pri, rules in self.priority_map.items()
            },
            "deterministic_enabled": sum(
                1 for rule in self.rules.values()
                if rule.deterministic_checks.required_keywords or 
                   rule.deterministic_checks.regex_patterns
            ),
            "llm_enabled": sum(
                1 for rule in self.rules.values()
                if rule.llm_prompt
            )
        }
        return stats


# Global rule manager instance
rule_manager = RuleManager()


def load_default_rules():
    """Load default rules from config directory"""
    config_dir = Path(__file__).parent.parent / "config"
    rules_file = config_dir / "sample_rules.json"
    
    if rules_file.exists():
        return rule_manager.load_rules(str(rules_file))
    else:
        logger.warning("No default rules file found")
        return []


def get_rule_manager() -> RuleManager:
    """Get global rule manager instance"""
    return rule_manager