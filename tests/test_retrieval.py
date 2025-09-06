from utils.retrieval import build_query_terms, retrieve_top_k_for_rule


def test_build_query_terms_dedup():
    rule = {"name": "Data Privacy", "description": "GDPR data privacy", "rule_text": "privacy personal data", "keywords": ["privacy", "gdpr"]}
    q = build_query_terms(rule)
    assert isinstance(q, list)
    # Ensure dedup and lowercase-ish behavior
    assert len(q) == len(set(q))


def test_retrieve_top_k_for_rule_basic():
    rule = {"name": "Indemnity", "description": "Indemnification", "rule_text": "indemnify party"}
    sentences = [
        "This agreement includes indemnification obligations.",
        "The term of this contract is one year.",
        "Indemnify and hold harmless provisions are present.",
        "Miscellaneous"
    ]
    results = retrieve_top_k_for_rule(rule, sentences, top_k=2)
    assert len(results) <= 2
    # Should include relevant chunks
    assert any("indemn" in (r.get("chunk", "").lower()) for r in results)


