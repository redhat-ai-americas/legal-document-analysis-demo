from __future__ import annotations

"""
Resilient model calling utilities that enforce schema adherence by:
- Validating JSON parses
- Validating allowed content values
- Appending corrective user messages and retrying when Granite drifts
"""

import json
from typing import Dict, Any, List, Tuple, Optional

from .granite_client import granite_client, GraniteAPIError


def _safe_json_parse(text: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    try:
        return json.loads(text), None
    except Exception as e:
        return None, str(e)


def _validate_schema_classification(payload: Dict[str, Any], allowed: List[str]) -> Tuple[bool, str]:
    # Expect {"class": [array of strings]}
    if not isinstance(payload, dict) or "class" not in payload:
        return False, "Missing 'class' key"
    klass = payload["class"]
    if not isinstance(klass, list):
        return False, "'class' must be an array of strings"
    for v in klass:
        if not isinstance(v, str):
            return False, "'class' array elements must be strings"
        if v not in allowed:
            return False, f"Invalid class value: {v}"
    return True, ""


DEFAULT_RETRY_MESSAGES = [
    (
        "Please correct your response to strictly follow the schema:\n"
        "Return only valid JSON with no prose.\n"
        "Schema: {\"class\": [array of strings]} where each value is one of [ball, brick, none]."
    ),
    (
        "Reminder: Respond with ONLY valid JSON. No text outside JSON.\n"
        "Ensure 'class' is an array of strings; allowed values: [ball, brick, none].\n"
        "If you cannot classify, return {\"class\": [\"none\"]}."
    ),
]


def call_with_schema_retry(
    system_message: str,
    user_message: str,
    allowed_classes: List[str],
    max_attempts: int = 3,
) -> Dict[str, Any]:
    """
    Call Granite and enforce output schema via iterative retries.
    - Validates JSON and content values
    - On failure, appends a corrective user message and retries
    Returns the parsed JSON on success or raises GraniteAPIError after attempts.
    """
    messages = [
        {"role": "system", "content": system_message},
        {"role": "user", "content": user_message},
    ]

    last_error = None
    for attempt in range(1, max_attempts + 1):
        try:
            result = granite_client.call_api_with_messages(messages, max_tokens=128, temperature=0.0, return_metadata=False)
            text = str(result)
            parsed, parse_err = _safe_json_parse(text)
            if parse_err:
                last_error = f"Attempt {attempt}: JSON parse error: {parse_err}; raw={text[:200]}"
            else:
                ok, why = _validate_schema_classification(parsed, allowed_classes)
                if ok:
                    return parsed
                last_error = f"Attempt {attempt}: schema/content validation failed: {why}; raw={text[:200]}"
        except GraniteAPIError as e:
            last_error = f"Attempt {attempt}: API error: {e}"

        # If not returned, append a corrective user message and retry
        corrective = DEFAULT_RETRY_MESSAGES[min(attempt - 1, len(DEFAULT_RETRY_MESSAGES) - 1)]
        messages.append({"role": "user", "content": corrective})

    raise GraniteAPIError(last_error or "Schema validation failed after retries")


def call_with_rules_schema_retry(messages: list, max_attempts: int = 3) -> Dict[str, Any]:
    """Enforce rules JSON schema via retries. Expects messages list ready for Granite.
    Schema: {"status": "compliant|non_compliant|not_applicable|unknown", "rationale": str, "violating_spans": [str], "citations": [int]}
    """
    allowed_status = {"compliant", "non_compliant", "not_applicable", "unknown"}
    last_error = None
    local_messages = list(messages)
    for attempt in range(1, max_attempts + 1):
        try:
            result = granite_client.call_api_with_messages(local_messages, max_tokens=256, temperature=0.0, return_metadata=False)
            text = str(result).strip()
            data = json.loads(text)
            status = str(data.get("status", "unknown")).lower()
            if status not in allowed_status:
                status = "unknown"
            data["status"] = status
            # Normalize arrays
            vs = data.get("violating_spans", [])
            ct = data.get("citations", [])
            if not isinstance(vs, list):
                vs = []
            if not isinstance(ct, list):
                ct = []
            # Coerce citations to ints when possible
            citations_norm: List[int] = []
            for c in ct:
                try:
                    citations_norm.append(int(c))
                except Exception:
                    continue
            data["violating_spans"] = [str(x) for x in vs if isinstance(x, (str, int, float))]
            data["citations"] = citations_norm
            return data
        except Exception as e:
            last_error = f"Attempt {attempt} failed: {e}"
            corrective = (
                "Reminder: Respond ONLY with valid JSON. Schema: {\"status\": \"compliant | non_compliant | not_applicable | unknown\", "
                "\"rationale\": \"...\", \"violating_spans\": [\"...\"], \"citations\": [1,2]}"
            )
            local_messages.append({"role": "user", "content": corrective})
    raise GraniteAPIError(last_error or "Rules schema validation failed after retries")


