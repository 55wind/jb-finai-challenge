"""② 규제 근거 검색 / RAG (F2).

기본: 토큰 중첩 + 카테고리 키워드 부스팅 기반 어휘 검색 (의존성 0, 결정적).
선택: sentence-transformers(BGE-m3)가 설치돼 있으면 임베딩 코사인 유사도로 자동 전환.
인용은 검색된 코퍼스 내 조항으로만 제한 → LLM 환각 인용 방지 (설계 문서 §15).
"""
from __future__ import annotations

import json
import math
import re
from pathlib import Path

_CORPUS_PATH = Path(__file__).resolve().parent.parent / "data" / "regulations.json"
_corpus_cache: list[dict] | None = None

SCORE_THRESHOLD = 0.05  # 이 미만이면 "근거 불충분" 처리 (허위 인용 방지)

# 어휘 검색이 짧은 광고 문구로도 관련 조항을 찾도록 카테고리 시드 키워드로 질의 확장
_QUERY_EXPANSION = [
    (r"확정|무조건|절대|100\s*%|guaranteed?", "단정적 판단 보장 확실 오인"),
    (r"원금|보장|principal|risk", "원금보장 손실보전 이익보장 예금자보호 한도"),
    (r"%|금리|이자|수익률|rate|returns?", "이자율 수익률 세전 세후 우대조건 변동"),
    (r"최고|최저|1\s*위|유일", "최상급 거짓 과장 비교 표시 광고"),
    (r"대출|승인|loan", "대출 연체이자율 중도상환수수료 심사"),
    (r"펀드|투자|fund|invest", "투자 원금손실 운용실적 투자설명서"),
]


def load_corpus() -> list[dict]:
    global _corpus_cache
    if _corpus_cache is None:
        with open(_CORPUS_PATH, encoding="utf-8") as f:
            _corpus_cache = json.load(f)
    return _corpus_cache


def get_article(article_id: str) -> dict | None:
    return next((a for a in load_corpus() if a["id"] == article_id), None)


def _tokenize(text: str) -> list[str]:
    return [t for t in re.split(r"[^0-9A-Za-z가-힣]+", text.lower()) if len(t) > 1]


def _expand_query(text: str) -> str:
    extra = [seed for pat, seed in _QUERY_EXPANSION if re.search(pat, text, re.IGNORECASE)]
    return text + " " + " ".join(extra)


def _lexical_scores(query: str, docs: list[dict]) -> list[float]:
    q_tokens = set(_tokenize(query))
    scores = []
    for doc in docs:
        d_tokens = _tokenize(doc["title"] + " " + doc["text"])
        if not d_tokens or not q_tokens:
            scores.append(0.0)
            continue
        overlap = sum(1 for t in d_tokens if t in q_tokens)
        scores.append(overlap / math.sqrt(len(d_tokens)) / math.sqrt(len(q_tokens)))
    return scores


_embedder = None
_doc_embeddings = None


def _try_embedding_scores(query: str, docs: list[dict]):
    """BGE-m3 임베딩 검색 (설치 시에만). 실패하면 None → 어휘 검색 폴백."""
    global _embedder, _doc_embeddings
    try:
        from sentence_transformers import SentenceTransformer  # optional
    except ImportError:
        return None
    try:
        if _embedder is None:
            _embedder = SentenceTransformer("BAAI/bge-m3")
            _doc_embeddings = _embedder.encode(
                [d["title"] + " " + d["text"] for d in load_corpus()], normalize_embeddings=True
            )
        q_emb = _embedder.encode([query], normalize_embeddings=True)[0]
        all_docs = load_corpus()
        idx = {d["id"]: i for i, d in enumerate(all_docs)}
        return [float(_doc_embeddings[idx[d["id"]]] @ q_emb) for d in docs]
    except Exception:
        return None


def retrieve(text: str, content_type: str, top_k: int = 4) -> dict:
    """초안 + 유형 → 관련 조항 top-k + 출처. {articles, backend, sufficient}"""
    docs = [a for a in load_corpus() if content_type in a["types"] or "common" in a["types"]]
    query = _expand_query(text)

    emb_scores = _try_embedding_scores(query, docs)
    backend = "bge-m3" if emb_scores is not None else "lexical"
    scores = emb_scores if emb_scores is not None else _lexical_scores(query, docs)

    ranked = sorted(zip(docs, scores), key=lambda x: x[1], reverse=True)
    hits = [
        {**doc, "score": round(score, 4)}
        for doc, score in ranked[:top_k]
        if score >= SCORE_THRESHOLD
    ]
    return {"articles": hits, "backend": backend, "sufficient": len(hits) > 0}
