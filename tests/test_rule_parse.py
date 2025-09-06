from nodes.rule_compliance_checker import _parse_result


def test_parse_result_valid_json():
    text = '{"status": "compliant", "rationale": "meets requirement"}'
    parsed = _parse_result(text)
    assert parsed["status"] == "compliant"
    assert "rationale" in parsed


def test_parse_result_invalid_json():
    text = 'not-json'
    parsed = _parse_result(text)
    assert parsed["status"] == "unknown"
    assert parsed["rationale"].startswith("parse_error") or parsed["rationale"] == "parse_error"


