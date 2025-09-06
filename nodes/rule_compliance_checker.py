from typing import Dict, Any, List
import json

from workflows.state import ContractAnalysisState
from utils.retrieval import env_top_k, get_candidates_for_rule
from utils.term_aliases import get_term_aliases
from utils.granite_client import GraniteAPIError
import os
from utils.model_calling import call_with_rules_schema_retry


def _format_target_clauses(candidates: List[Dict[str, Any]]) -> str:
	lines: List[str] = []
	for i, cand in enumerate(candidates, 1):
		chunk = cand.get("chunk", "").strip()
		if not chunk:
			continue
		lines.append(f"{i}. {chunk}")
	return "\n".join(lines)


def _load_prompt_template() -> Dict[str, Any]:
	base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
	path = os.path.join(base_dir, "prompts", "rule_compliance.yaml")
	with open(path, "r", encoding="utf-8") as f:
		import yaml
		return yaml.safe_load(f)


def _build_prompt(rule: Dict[str, Any], candidates: List[Dict[str, Any]], template: Dict[str, Any]) -> str:
	target_clauses = _format_target_clauses(candidates)
	raw = template.get("template", "")
	# Escape all braces then unescape known placeholders to avoid KeyError on JSON braces
	escaped = raw.replace("{", "{{").replace("}", "}}")
	for key in ("rule_name", "rule_description", "rule_text", "default_status", "target_clauses"):
		escaped = escaped.replace("{{" + key + "}}", "{" + key + "}")
	return escaped.format(
		rule_name=rule.get("name", ""),
		rule_description=rule.get("description", ""),
		rule_text=rule.get("rule_text", ""),
		default_status=rule.get("default_status", "unknown"),
		target_clauses=target_clauses or "No relevant clauses found."
	)


def _parse_result(text: str) -> Dict[str, Any]:
	try:
		data = json.loads(text)
		# Minimal normalization
		status = str(data.get("status", "unknown")).lower()
		if status not in {"compliant", "non_compliant", "not_applicable", "unknown"}:
			status = "unknown"
		data["status"] = status
		return data
	except Exception:
		return {
			"status": "unknown",
			"rationale": "parse_error",
			"violating_spans": [],
			"citations": [],
		}


def _extract_anchor(text: str) -> str:
	"""Extract [[page=N]] anchor if present."""
	import re as _re
	match = _re.search(r"\[\[page=(\d+)]]", text or "")
	return f"[[page={match.group(1)}]]" if match else ""


def _resolve_citations(parsed: Dict[str, Any], candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
	"""Map numeric citations to direct-quote objects with anchors."""
	resolved: List[Dict[str, Any]] = []
	indices = parsed.get("citations", []) or []
	if not isinstance(indices, list):
		return resolved
	for idx in indices:
		try:
			i = int(idx) - 1
			if 0 <= i < len(candidates):
				chunk = candidates[i].get("chunk", "")
				anchor = _extract_anchor(chunk)
				resolved.append({"text": chunk, "anchor": anchor})
		except Exception:
			continue
	return resolved


def _keywords_for_rule(rule: Dict[str, Any]) -> List[str]:
	name_text = " ".join([str(rule.get("id", "")), str(rule.get("name", ""))]).lower()
	rule_text = (rule.get("rule_text", "") or "").lower()
	if any(k in name_text for k in ["mfn", "mfc", "most favored", "most favoured"]):
		return ["most favored", "most favoured", "mfn", "mfc", "matching", "equal or better", "best pricing", "comparable pricing"]
	if any(k in name_text for k in ["exclusiv", "non-compete", "noncompete"]):
		return ["exclusive", "exclusivity", "sole provider", "non-compete", "noncompete"]
	if any(k in name_text for k in ["assign", "change of control", "coc"]):
		return ["assign", "assignment", "change of control", "coc"]
	if any(k in name_text for k in ["liability", "limitation of liability", "cap"]):
		return ["limitation of liability", "liability cap", "cap on liability", "indirect damages", "consequential damages", "lost profits"]
	# fallback: derive from rule text tokens
	return [w for w in rule_text.split() if len(w) > 4][:8]


def _deterministic_eval(rule: Dict[str, Any], sentences: List[str]) -> Dict[str, Any]:
	"""Attempt deterministic evaluation based on simple keyword/intent heuristics.

	Returns empty dict if inconclusive; otherwise a partial result with status, rationale, violating_spans, citations, attribution.
	"""
	if not sentences:
		return {}
	kw = _keywords_for_rule(rule)
	if not kw:
		return {}
	text = (rule.get("rule_text", "") or "").lower()
	intent_prohibit = any(p in text for p in ["must not", "prohibit", "shall not", "no "])
	intent_require = (not intent_prohibit) and any(p in text for p in ["must ", "shall ", "require "])

	# Find matching sentences for evidence
	matches: List[str] = []
	for s in sentences:
		low = s.lower()
		if any(k in low for k in kw):
			matches.append(s.strip())

	if not matches:
		return {}

	# Build citations as direct quotes
	citations = [{"text": m, "anchor": _extract_anchor(m)} for m in matches[:5]]
	spans = matches[:3]

	if intent_prohibit:
		return {
			"status": "non_compliant",
			"rationale": "Deterministic match: prohibited terms present in contract.",
			"violating_spans": spans,
			"citations": citations,
			"attribution": "deterministic",
		}
	if intent_require:
		return {
			"status": "compliant",
			"rationale": "Deterministic match: required terms present in contract.",
			"violating_spans": [],
			"citations": citations,
			"attribution": "deterministic",
		}
	return {}


def rule_compliance_checker(state: ContractAnalysisState) -> Dict[str, Any]:
	"""Evaluate rules against the target document using Granite 3.3.

	Inputs (from state):
	- document_sentences
	- rules_data

	Outputs:
	- rule_compliance_results (final status per rule)
	- rule_violations (non-compliant findings)
	- compliance_metrics (counts by status)
	"""
	rules = state.get("rules_data", []) or []
	print(f"  🧭 rule_compliance_checker: rules_count={len(rules)}")
	# Defensive reload if previous node's updates were not merged correctly
	if not rules:
		rules_path = state.get("rules_path") or ""
		if rules_path and os.path.exists(rules_path):
			try:
				ext = os.path.splitext(rules_path)[1].lower()
				loaded: List[Dict[str, Any]] = []
				if ext in (".json",):
					with open(rules_path, "r", encoding="utf-8") as f:
						data = json.load(f)
						items = data.get("rules", data) if isinstance(data, dict) else data
						loaded = items if isinstance(items, list) else []
				elif ext in (".yml", ".yaml"):
					try:
						import yaml  # type: ignore
						with open(rules_path, "r", encoding="utf-8") as f:
							data = yaml.safe_load(f) or []
						items = data.get("rules", data) if isinstance(data, dict) else data
						loaded = items if isinstance(items, list) else []
					except Exception:
						loaded = []
				# Minimal normalization: ensure dicts
				if loaded and isinstance(loaded, list) and all(isinstance(x, dict) for x in loaded):
					rules = loaded
					state["rules_data"] = rules
					print(f"  🔄 rule_compliance_checker: reloaded rules ({len(rules)}) from {rules_path}")
			except Exception as re:
				print(f"  ⚠️  rule_compliance_checker: failed to reload rules from {rules_path}: {re}")
	document_sentences = state.get("document_sentences", []) or []
	document_text = state.get("document_text", "") or ""

	results: List[Dict[str, Any]] = []
	violations: List[Dict[str, Any]] = []
	k = env_top_k(8)

	template = _load_prompt_template()

	get_term_aliases()
	any_fallback_used = False
	for rule in rules:
		# Deterministic-first evaluation
		det = _deterministic_eval(rule, document_sentences)
		candidates, fallback_used = get_candidates_for_rule(rule, document_sentences, document_text, top_k=k, window=1)
		if fallback_used:
			any_fallback_used = True
		prompt = _build_prompt(rule, candidates, template)
		try:
			messages = [
				{"role": "system", "content": "You are a contract compliance checker. Return ONLY JSON adhering to the schema."},
				{"role": "user", "content": prompt},
			]
			parsed = call_with_rules_schema_retry(messages, max_attempts=3) if not det else det
		except GraniteAPIError as e:
			parsed = {
				"status": "unknown",
				"rationale": f"api_error: {e}",
				"violating_spans": [],
				"citations": [],
				}

		entry = {
			"rule_id": rule.get("id"),
			"severity": rule.get("severity"),
			"status": parsed.get("status", "unknown"),
			"rationale": parsed.get("rationale", ""),
			"citations": parsed.get("citations", []),
			"violating_spans": parsed.get("violating_spans", []),
			"retrieval": {
				"top_k": k,
				"candidates": candidates,
				"fallback_used": fallback_used,
			},
		}
		results.append(entry)

		if entry["status"] == "non_compliant":
			violations.append(entry)

	# Metrics
	counts = {"compliant": 0, "non_compliant": 0, "not_applicable": 0, "unknown": 0}
	for r in results:
		counts[r.get("status", "unknown")] = counts.get(r.get("status", "unknown"), 0) + 1

	metrics = {
		"total_rules": len(rules),
		"retrieval_top_k": k,
		"counts": counts,
		"violations": len(violations),
	}

	return {
		"rule_compliance_results": results,
		"rule_violations": violations,
		"compliance_metrics": metrics,
		"rules_mode": {
			"enabled": True,
			"executed": True,
			"retrieval_fallback_used": any_fallback_used,
		},
	}
