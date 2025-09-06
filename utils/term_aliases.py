"""
Term alias utilities to align questionnaire/retrieval topics with classifier labels.

Provides:
- get_term_aliases(): canonical term -> set of alias strings
- rule_id_to_canonical(term_or_rule_id): maps rule IDs/names to canonical term keys
"""
from __future__ import annotations

from typing import Dict, Set


def get_term_aliases() -> Dict[str, Set[str]]:
    # Canonical -> aliases (lowercase)
    return {
        # Questionnaire canonical terms
        "intellectual_property_rights": {
            "intellectual_property_rights", "ip_rights", "ip", "intellectual_property",
        },
        "assignment_change_of_control": {
            "assignment_change_of_control", "change_of_control", "coc", "assignment", "assign",
        },
        "most_favored_nation": {
            "most_favored_nation", "mfn", "mfc", "favored_pricing", "most_favored",
            "best_pricing", "equal_or_better", "matching", "comparable_pricing",
        },
        "limitation_of_liability": {
            "limitation_of_liability", "liability_cap", "indirect_damages", "consequential_damages",
            "lost_profits", "special_damages", "exemplary_damages",
        },
        "indemnification": {
            "indemnification", "indemnity", "indemnify",
        },
        "non_compete_exclusivity": {
            "non_compete_exclusivity", "non_compete", "exclusivity", "exclusive", "exclusive_rights",
        },
        "source_code_escrow": {
            "source_code_escrow", "escrow", "source_code",
        },
        "term": {
            "term", "effective_date", "start_date", "initial_term", "duration",
        },

        # Data/privacy related
        "data_processing_agreement": {
            "data_processing_agreement", "dpa", "processing_activities", "subprocessor", "tom",
            "technical_and_organizational_measures",
        },
        "data_breach": {"data_breach", "breach_notification", "immediate_notification", "fixed_timeframe"},
        "data_transfer": {"data_transfer", "sub_processor", "subprocessor"},
    }


def rule_id_to_canonical(rule_id: str) -> str:
    rid = (rule_id or "").lower().strip()
    # Normalize common rule ids to canonical term keys used in classification
    mapping = {
        "intellectual_property_ip_rights": "intellectual_property_rights",
        "limitation_of_liability": "limitation_of_liability",
        "most_favored_nation": "most_favored_nation",
        "indemnification": "indemnification",
        "assignment": "assignment_change_of_control",
        "change_of_control": "assignment_change_of_control",
        "non_compete_exclusivity": "non_compete_exclusivity",
        "source_code_escrow": "source_code_escrow",
        "data_processing_agreement": "data_processing_agreement",
        "data_breach": "data_breach",
        "data_transfer": "data_transfer",
        # Fallback: return rule id itself
    }
    return mapping.get(rid, rid)


def alias_to_canonical(term: str) -> str:
    """Map any alias or canonical label to its canonical term key; returns original if unknown."""
    t = (term or "").lower().strip()
    aliases = get_term_aliases()
    # direct match to a canonical key
    if t in aliases:
        return t
    # search aliases
    for canonical, alias_set in aliases.items():
        if t in alias_set:
            return canonical
    return term


