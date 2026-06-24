"""
Domain knowledge search over expert interview transcripts.

Transcripts live in data/transcripts/ as a git submodule
(AidanJanney/RegionalOceanModelingInterviews) containing:
- data/merged_for_finetuning.jsonl  — Q&A pairs, one per line
- transcripts/Edited_Transcript_*.json — full interview conversations

At startup we load all Q&A pairs into memory for fast keyword search.
The search is intentionally simple (keyword overlap) so it works without
any ML dependencies — fast, transparent, and easy to extend.
"""

import json
import re
import os
from pathlib import Path
from functools import lru_cache

# Path to transcript data, relative to this file's package root
_SCRIPT_DIR = Path(__file__).parent.parent
_TRANSCRIPTS_DIR = _SCRIPT_DIR / "data" / "transcripts"
_MERGED_JSONL = _TRANSCRIPTS_DIR / "data" / "merged_for_finetuning.jsonl"


@lru_cache(maxsize=1)
def _load_knowledge() -> list[dict]:
    """Load all Q&A pairs from merged JSONL. Cached after first call."""
    if not _MERGED_JSONL.exists():
        return []

    pairs = []
    with open(_MERGED_JSONL) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                msgs = obj.get("messages", [])
                if len(msgs) >= 2:
                    q = next((m["content"] for m in msgs if m["role"] == "user"), "")
                    a = next((m["content"] for m in msgs if m["role"] == "assistant"), "")
                    if q and a:
                        pairs.append({"question": q, "answer": a})
            except json.JSONDecodeError:
                continue
    return pairs


def _score(query: str, pair: dict) -> int:
    """Simple keyword overlap score between query and a Q&A pair."""
    query_words = set(re.findall(r"\b\w{3,}\b", query.lower()))
    text = (pair["question"] + " " + pair["answer"]).lower()
    text_words = set(re.findall(r"\b\w{3,}\b", text))
    return len(query_words & text_words)


def query_domain_knowledge(question: str, top_k: int = 5) -> str:
    """
    Search expert interview transcripts for scientific guidance on a question.

    The knowledge base contains interviews with regional ocean modelling experts
    covering topics like: MOM6 configuration, OBC setup, tidal forcing, bathymetry,
    stability, BGC, grid design, known failure modes, and regional ocean dynamics.

    Returns the top matching Q&A pairs from the expert interviews.
    top_k: number of results to return (default 5, max 10).
    """
    pairs = _load_knowledge()
    if not pairs:
        return (
            "Knowledge base not available. "
            "Ensure data/transcripts/ submodule is initialised:\n"
            "  git submodule update --init --remote data/transcripts"
        )

    top_k = min(top_k, 10)
    scored = [(pair, _score(question, pair)) for pair in pairs]
    scored.sort(key=lambda x: x[1], reverse=True)
    top = [pair for pair, score in scored[:top_k] if score > 0]

    if not top:
        return (
            f"No relevant Q&A pairs found for: '{question}'.\n"
            "Try rephrasing with different keywords (e.g. 'CFL', 'OBC', 'tides', 'bathymetry')."
        )

    lines = [f"Top {len(top)} results for: '{question}'\n"]
    for i, pair in enumerate(top, 1):
        lines.append(f"--- Result {i} ---")
        lines.append(f"Q: {pair['question'].strip()}")
        lines.append(f"A: {pair['answer'].strip()}")
        lines.append("")

    return "\n".join(lines)


def get_parameter_advice(param_name: str) -> str:
    """
    Look up expert guidance for a specific MOM6 parameter name.

    Searches the interview knowledge base for mentions of the parameter,
    along with context about what it does, typical values, and pitfalls.

    param_name: MOM6 parameter name (e.g. 'DT', 'MINIMUM_DEPTH', 'OBC_SEGMENTS',
                'SPONGE', 'TIDES', 'KD_MAX', 'KHTH').
    """
    pairs = _load_knowledge()
    if not pairs:
        return (
            "Knowledge base not available. "
            "Ensure data/transcripts/ submodule is initialised:\n"
            "  git submodule update --init --remote data/transcripts"
        )

    param_lower = param_name.lower()
    # Search specifically for parameter name mentions
    hits = []
    for pair in pairs:
        combined = (pair["question"] + " " + pair["answer"]).lower()
        if param_lower in combined:
            hits.append(pair)

    if not hits:
        # Fall back to keyword search
        return query_domain_knowledge(param_name, top_k=3)

    lines = [f"Expert guidance for parameter: {param_name}\n"]
    for i, pair in enumerate(hits[:5], 1):
        lines.append(f"--- Excerpt {i} ---")
        lines.append(f"Q: {pair['question'].strip()}")
        lines.append(f"A: {pair['answer'].strip()}")
        lines.append("")

    return "\n".join(lines)
