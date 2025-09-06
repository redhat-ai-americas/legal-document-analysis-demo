#!/usr/bin/env python3
"""
Quick tests for alias-aware questionnaire retrieval and rules paragraph fallback retrieval.
Runs in isolation without calling any LLM APIs.
"""
import os
import sys

# Ensure package root on sys.path
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PKG_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
if PKG_ROOT not in sys.path:
    sys.path.append(PKG_ROOT)

from typing import Dict, Any, List

from nodes.questionnaire_processor_enhanced import get_relevant_sentences_with_attribution
from utils.retrieval import fallback_retrieve_top_k_from_text


def test_questionnaire_alias_retrieval() -> None:
    print("\n=== Test: Questionnaire alias-aware retrieval (ip -> intellectual_property_rights) ===")

    # Minimal terminology with canonical terms
    terminology_data: Dict[str, Any] = {
        "terms": [
            {"name": "intellectual_property_rights"},
            {"name": "assignment_change_of_control"},
            {"name": "most_favored_nation"},
            {"name": "limitation_of_liability"},
            {"name": "indemnification"},
            {"name": "non_compete_exclusivity"},
            {"name": "source_code_escrow"},
            {"name": "term"},
            {"name": "document_type"},
        ]
    }

    # Classified sentences using a short alias label "ip"
    target_classified: List[Dict[str, Any]] = [
        {
            "sentence": "IP ownership remains with Supplier; Customer receives a non-exclusive license.",
            "classes": ["ip"],
            "confidence": 0.8,
            "sentence_id": 1,
            "page_number": 2,
            "section_name": "Intellectual Property"
        }
    ]

    target_sentences, reference_sentences, searched_terms = get_relevant_sentences_with_attribution(
        "ip_rights", target_classified, [], terminology_data
    )

    print(f"Searched terms: {searched_terms}")
    print(f"Target sentences found: {len(target_sentences)}")
    if target_sentences:
        print(f"First hit: {target_sentences[0].get('sentence')}")


def test_rules_paragraph_fallback() -> None:
    print("\n=== Test: Rules paragraph fallback retrieval (MFN keywords in raw text) ===")

    # Minimal MFN-like rule object
    rule = {
        "id": "most_favored_nation",
        "name": "Most Favored Nation",
        "description": "A clause where the supplier promises the customer the best pricing or terms it offers to any customer",
        "rule_text": "Contract must not contain Most Favored Nation or matching discount/terms provision.",
        "keywords": ["most", "favored", "nation", "matching", "pricing", "discount"],
        "default_status": "compliant",
    }

    # Raw text contains MFN-related phrases
    document_text = (
        "The Supplier shall not be obligated to offer Most Favored Nation pricing.\n\n"
        "Customer acknowledges no matching discount or equal or better pricing obligations apply.\n\n"
        "Pricing is determined independently without comparable pricing guarantees."
    )

    candidates = fallback_retrieve_top_k_from_text(rule, document_text, top_k=5, paragraph_window=2)
    print(f"Candidates found: {len(candidates)}")
    if candidates:
        print("Top candidate snippet:\n" + candidates[0]["chunk"][:300])


if __name__ == "__main__":
    test_questionnaire_alias_retrieval()
    test_rules_paragraph_fallback()
    print("\nAll tests executed.")


