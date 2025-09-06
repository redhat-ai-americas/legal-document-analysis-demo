"""
Rule schema definitions and validation helpers for rules ingestion.
"""
from __future__ import annotations

from typing import Dict, Any, List, Tuple, Optional
import re

REQUIRED_FIELDS = ["name", "rule_text"]
ALLOWED_DEFAULTS = {"compliant", "non_compliant", "not_applicable", "unknown"}
ALLOWED_SEVERITY = {"low", "medium", "high"}


def normalize_header(header: str) -> str:
    return (header or "").strip().lower().replace(" ", "_")


def _safe_str(value: Any) -> str:
    return (str(value) if value is not None else "").strip()


def _slugify(text: str, fallback: str = "rule") -> str:
    text = _safe_str(text)
    if not text:
        return fallback
    # Keep alphanumerics and underscores; replace separators with underscore
    text = re.sub(r"[^a-zA-Z0-9\s_-]", "", text)
    text = text.strip().lower().replace(" ", "_").replace("-", "_")
    # Collapse duplicates
    text = re.sub(r"_+", "_", text)
    return text or fallback


def derive_keywords_if_missing(name: str, description: str) -> List[str]:
    """Very simple keyword derivation from name/description if not provided."""
    tokens = re.split(r"[\s,/;]+", f"{name} {description}".strip().lower())
    # Filter trivial tokens
    keywords = [t for t in tokens if len(t) > 3]
    # De-duplicate preserving order
    seen = set()
    result: List[str] = []
    for k in keywords:
        if k not in seen:
            seen.add(k)
            result.append(k)
    return result[:6]


def coerce_default_status(value: str) -> str:
    v = _safe_str(value).lower()
    # Map common synonyms
    mapping = {
        "yes": "compliant",
        "no": "non_compliant",
        "n/a": "not_applicable",
        "na": "not_applicable",
        "default": "unknown",
    }
    v = mapping.get(v, v)
    return v if v in ALLOWED_DEFAULTS else "unknown"


def coerce_severity(value: str) -> Optional[str]:
    v = _safe_str(value).lower()
    return v if v in ALLOWED_SEVERITY else None


def normalize_rule_row(row: Dict[str, Any]) -> Dict[str, Any]:
    name = _safe_str(row.get("name") or row.get("rule_name"))
    description = _safe_str(row.get("description") or row.get("rule_description"))
    rule_text = _safe_str(row.get("rules") or row.get("rule_text"))
    default_status = coerce_default_status(row.get("default") or row.get("default_status") or "unknown")
    severity = coerce_severity(row.get("severity") or "")

    # keywords/exceptions can be CSV string or list
    keywords_raw = row.get("keywords")
    if isinstance(keywords_raw, str):
        keywords = [k.strip() for k in keywords_raw.split(",") if k.strip()]
    else:
        keywords = list(keywords_raw or [])

    exceptions_raw = row.get("exceptions")
    if isinstance(exceptions_raw, str):
        exceptions = [e.strip() for e in exceptions_raw.split(",") if e.strip()]
    else:
        exceptions = list(exceptions_raw or [])

    if not keywords:
        keywords = derive_keywords_if_missing(name, description)

    rule_id_source = name or rule_text[:32]
    rule_id = _slugify(rule_id_source, fallback="rule")

    return {
        "id": rule_id,
        "name": name,
        "description": description,
        "rule_text": rule_text,
        "default_status": default_status,
        "severity": severity,
        "keywords": keywords,
        "exceptions": exceptions,
    }


def validate_rule(rule: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    if not rule.get("name") and not rule.get("rule_text"):
        errors.append("Either 'Name' or 'Rules' (rule_text) must be provided")
    if not rule.get("rule_text"):
        errors.append("Missing 'Rules' (operative constraint) field")
    if rule.get("default_status") not in ALLOWED_DEFAULTS:
        errors.append(
            f"Invalid default status '{rule.get('default_status')}'. Allowed: {sorted(ALLOWED_DEFAULTS)}"
        )
    if rule.get("severity") not in ALLOWED_SEVERITY | {None}:
        errors.append(
            f"Invalid severity '{rule.get('severity')}'. Allowed: {sorted(ALLOWED_SEVERITY)} or empty"
        )
    return errors


def validate_rules(rules: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[str]]:
    valid: List[Dict[str, Any]] = []
    issues: List[str] = []
    for idx, r in enumerate(rules, start=1):
        errs = validate_rule(r)
        if errs:
            for e in errs:
                issues.append(f"Row {idx}: {e}")
        else:
            valid.append(r)
    return valid, issues
