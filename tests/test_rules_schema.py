from utils import rules_schema


def test_normalize_rule_row_minimal():
    row = {
        "name": "Most Favored Nation",
        "rule_text": "Customer shall offer MFN pricing to Vendor.",
        "default_status": "Yes",
        "severity": "High",
        "keywords": "pricing, discount, mfn"
    }
    normalized = rules_schema.normalize_rule_row(row)
    assert normalized["id"].startswith("most_favored_nation")
    assert normalized["default_status"] == "compliant"
    assert normalized["severity"] == "high"
    assert "pricing" in normalized["keywords"]


def test_validate_rules_collects_errors():
    items = [
        {"name": "", "rule_text": ""},
        {"name": "Valid", "rule_text": "Must include X"},
    ]
    valid, issues = rules_schema.validate_rules([rules_schema.normalize_rule_row(i) for i in items])
    # One should be valid, one should have issues
    assert len(valid) == 1
    assert any("Missing 'Rules'" in msg or "Either 'Name'" in msg for msg in issues)


