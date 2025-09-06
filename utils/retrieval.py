"""
Retrieval utilities for selecting candidate clauses per rule.
- Simple BM25-like scorer implemented without extra dependencies
- Windowed chunking to merge adjacent sentences
"""
from __future__ import annotations

from typing import List, Dict, Any, Tuple, Optional
import math
import re
import os
import json

DEFAULT_K1 = 1.5
DEFAULT_B = 0.75


def _tokenize(text: str) -> List[str]:
    text = (text or "").lower()
    # Simple tokenization: alphanumerics only
    tokens = re.findall(r"[a-z0-9_]+", text)
    return tokens


def _build_index(sentences: List[str]) -> Tuple[List[List[str]], Dict[str, int], float]:
    tokenized: List[List[str]] = [_tokenize(s) for s in sentences]
    df: Dict[str, int] = {}
    for terms in tokenized:
        seen = set()
        for t in terms:
            if t in seen:
                continue
            seen.add(t)
            df[t] = df.get(t, 0) + 1
    avgdl = sum(len(terms) for terms in tokenized) / (len(tokenized) or 1)
    return tokenized, df, avgdl


def _bm25_score(query_terms: List[str], terms: List[str], df: Dict[str, int], N: int, avgdl: float, k1: float, b: float) -> float:
    if not terms:
        return 0.0
    score = 0.0
    doclen = len(terms)
    tf_counts: Dict[str, int] = {}
    for t in terms:
        tf_counts[t] = tf_counts.get(t, 0) + 1
    for q in query_terms:
        if q not in df:
            continue
        n_q = df[q]
        idf = math.log((N - n_q + 0.5) / (n_q + 0.5) + 1.0)
        tf = tf_counts.get(q, 0)
        denom = tf + k1 * (1 - b + b * (doclen / (avgdl or 1)))
        score += idf * (tf * (k1 + 1)) / (denom or 1)
    return score


def _merge_window(sentences: List[str], center_idx: int, window: int) -> Tuple[str, List[int]]:
    if window <= 0:
        return sentences[center_idx], [center_idx]
    start = max(0, center_idx - window)
    end = min(len(sentences) - 1, center_idx + window)
    indices = list(range(start, end + 1))
    chunk = "\n".join(sentences[i] for i in indices)
    return chunk, indices


def build_query_terms(rule: Dict[str, Any]) -> List[str]:
    terms: List[str] = []
    for field in ("name", "description", "rule_text"):
        val = rule.get(field) or ""
        terms.extend(_tokenize(val))
    for kw in rule.get("keywords", []) or []:
        terms.extend(_tokenize(kw))
    # Deduplicate while preserving order
    seen = set()
    q: List[str] = []
    for t in terms:
        if t not in seen:
            seen.add(t)
            q.append(t)
    return q


def retrieve_top_k_for_rule(
    rule: Dict[str, Any],
    sentences: List[str],
    top_k: int = 8,
    window: int = 0,
    k1: float = DEFAULT_K1,
    b: float = DEFAULT_B,
) -> List[Dict[str, Any]]:
    """
    Returns list of candidates: {index, score, chunk, sentence_indices}
    """
    if not sentences:
        return []
    query_terms = build_query_terms(rule)
    tokenized, df, avgdl = _build_index(sentences)
    N = len(tokenized)

    scored: List[Tuple[int, float]] = []
    for idx, terms in enumerate(tokenized):
        score = _bm25_score(query_terms, terms, df, N, avgdl, k1, b)
        if score > 0:
            scored.append((idx, score))

    scored.sort(key=lambda x: x[1], reverse=True)
    results: List[Dict[str, Any]] = []
    seen_spans = set()
    for idx, score in scored[: max(top_k * (window * 2 + 1), top_k)]:
        chunk, indices = _merge_window(sentences, idx, window)
        span_key = (indices[0], indices[-1])
        if span_key in seen_spans:
            continue
        seen_spans.add(span_key)
        results.append({
            "index": idx,
            "score": float(score),
            "chunk": chunk,
            "sentence_indices": indices,
        })
        if len(results) >= top_k:
            break
    return results


def env_top_k(default: int = 8) -> int:
    try:
        return int(os.getenv("RULES_TOP_K", str(default)))
    except Exception:
        return default


def _env_bool(name: str, default: bool = False) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return str(val).lower() in {"1", "true", "yes", "on"}


def _env_float(name: str, default: float = 0.5) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except Exception:
        return default


def _normalize_scores(values: List[float]) -> List[float]:
    if not values:
        return []
    maxv = max(values)
    if maxv <= 0:
        return [0.0 for _ in values]
    return [v / maxv for v in values]


def _cosine_similarity(a: List[float], b: List[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def _maybe_get_embeddings_for_texts(texts: List[str]) -> Optional[List[List[float]]]:
    """Return embeddings if USE_EMBEDDINGS and GRANITE_EMBEDDING_URL are set; else None."""
    use_embeddings = _env_bool("USE_EMBEDDINGS", False)
    embed_url = os.getenv("GRANITE_EMBEDDING_URL")
    if not use_embeddings or not embed_url:
        return None
    try:
        import requests  # Lazy import to avoid dependency when unused
    except Exception:
        print("  WARNING: requests not available; disabling embeddings retrieval")
        return None

    # Simple caching by hash of concatenated texts length+checksum
    doc_key = f"len={len(texts)}:sum={sum(len(t) for t in texts)}"
    cache_dir = os.path.join("data", "indexes")
    os.makedirs(cache_dir, exist_ok=True)
    cache_path = os.path.join(cache_dir, f"emb_{abs(hash(doc_key))}.json")

    if os.path.exists(cache_path):
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                cached = json.load(f)
            if isinstance(cached, list) and len(cached) == len(texts):
                return cached
        except Exception:
            pass

    try:
        payload = {"inputs": texts}
        resp = requests.post(embed_url, json=payload, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        # Expect list of vectors
        if isinstance(data, list) and data and isinstance(data[0], list):
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(data, f)
            return data
        print("  WARNING: Unexpected embedding response format; disabling embeddings")
        return None
    except Exception as e:
        print(f"  WARNING: Embedding request failed: {e}")
        return None


def retrieve_top_k_hybrid(
    rule: Dict[str, Any],
    sentences: List[str],
    top_k: int = 8,
    window: int = 0,
    alpha: float = None,
    k1: float = DEFAULT_K1,
    b: float = DEFAULT_B,
) -> List[Dict[str, Any]]:
    """Hybrid retrieval using BM25 plus optional embedding similarity.

    score = alpha * cosine + (1 - alpha) * normalized_bm25
    If embeddings are unavailable, falls back to BM25 only.
    """
    if not sentences:
        return []

    if alpha is None:
        alpha = _env_float("HYBRID_ALPHA", 0.5)

    # BM25 baseline
    query_terms = build_query_terms(rule)
    tokenized, df, avgdl = _build_index(sentences)
    N = len(tokenized)
    bm25_scores: List[float] = []
    for terms in tokenized:
        bm25_scores.append(_bm25_score(query_terms, terms, df, N, avgdl, k1, b))
    bm25_norm = _normalize_scores(bm25_scores)

    # Optional embeddings
    hybrid_scores: List[float] = list(bm25_norm)
    embeddings = _maybe_get_embeddings_for_texts(sentences)
    if embeddings is not None:
        # Build a query embedding from rule name+text
        rule_text = " ".join([rule.get("name", ""), rule.get("rule_text", ""), rule.get("description", "")]).strip()
        qe = _maybe_get_embeddings_for_texts([rule_text])
        if qe and isinstance(qe, list) and len(qe) == 1:
            qv = qe[0]
            cosims = [
                _cosine_similarity(qv, sv) if isinstance(sv, list) else 0.0
                for sv in embeddings
            ]
            cos_norm = _normalize_scores(cosims)
            hybrid_scores = [alpha * cos + (1 - alpha) * bm for cos, bm in zip(cos_norm, bm25_norm)]

    # Rank and window merge
    ranked = sorted(list(enumerate(hybrid_scores)), key=lambda x: x[1], reverse=True)
    results: List[Dict[str, Any]] = []
    seen_spans = set()
    for idx, score in ranked:
        if score <= 0:
            continue
        chunk, indices = _merge_window(sentences, idx, window)
        span_key = (indices[0], indices[-1])
        if span_key in seen_spans:
            continue
        seen_spans.add(span_key)
        results.append({
            "index": idx,
            "score": float(score),
            "chunk": chunk,
            "sentence_indices": indices,
        })
        if len(results) >= top_k:
            break
    return results


def get_candidates_for_rule(
    rule: Dict[str, Any],
    sentences: List[str],
    document_text: str,
    top_k: int = 8,
    window: int = 1,
) -> Tuple[List[Dict[str, Any]], bool]:
    """Unified candidate selection with hybrid retrieval and paragraph fallback.

    Returns (candidates, fallback_used)
    """
    if not sentences and not document_text:
        return [], False

    # Hybrid retrieval over sentences
    candidates = retrieve_top_k_hybrid(rule, sentences, top_k=top_k, window=window)
    if candidates:
        return candidates, False

    # Paragraph/text fallback
    if document_text:
        fallback = fallback_retrieve_top_k_from_text(rule, document_text, top_k=top_k, paragraph_window=2)
        if fallback:
            return fallback, True

    return [], False
def fallback_retrieve_top_k_from_text(
    rule: Dict[str, Any],
    document_text: str,
    top_k: int = 8,
    paragraph_window: int = 1,
) -> List[Dict[str, Any]]:
    """
    Fallback retrieval when sentence-level retrieval yields no candidates.
    Scans raw markdown/text by paragraphs using keyword presence, and returns merged windows.
    Returns list of candidates: {index, score, chunk, sentence_indices}
    Note: sentence_indices here refer to paragraph indices for lack of sentence segmentation.
    """
    if not document_text:
        return []
    query_terms = set(build_query_terms(rule))
    paragraphs = [p.strip() for p in document_text.split("\n\n") if p.strip()]
    scored: List[Tuple[int, float]] = []
    for idx, p in enumerate(paragraphs):
        toks = set(_tokenize(p))
        overlap = len(query_terms.intersection(toks))
        if overlap > 0:
            # Simple score: term overlap weighted by length
            score = overlap / max(5, len(toks))
            scored.append((idx, score))
    scored.sort(key=lambda x: x[1], reverse=True)
    results: List[Dict[str, Any]] = []
    seen_spans = set()
    for idx, score in scored:
        start = max(0, idx - paragraph_window)
        end = min(len(paragraphs) - 1, idx + paragraph_window)
        span_key = (start, end)
        if span_key in seen_spans:
            continue
        seen_spans.add(span_key)
        chunk = "\n".join(paragraphs[i] for i in range(start, end + 1))
        results.append({
            "index": idx,
            "score": float(score),
            "chunk": chunk,
            "sentence_indices": list(range(start, end + 1)),
        })
        if len(results) >= top_k:
            break
    return results
