"""
Word Map Lite.

Builds a lightweight concept graph from buckets and moments. This is for
observation and weak future assistance; it is not evidence and does not bypass
recall filters.
"""

import json
import re
from collections import Counter, defaultdict
from datetime import datetime
from itertools import combinations
from pathlib import Path
from typing import Dict, List

from .memory import memory_system
from .memory_graph import list_moments

WORD_MAP_DIR = Path("./memory/word_map")
WORD_MAP_PATH = WORD_MAP_DIR / "word_map.json"

STOPWORDS = {
    "the", "and", "for", "with", "this", "that", "you", "are", "was", "have", "has",
    "user", "project", "memory", "mem", "conversation", "auto_moment", "dynamic", "permanent",
    "?", "?", "?", "?", "?", "?", "?", "?", "?", "?", "?", "?", "?", "?", "?", "?",
    "??", "??", "??", "??", "??", "??", "??", "??", "??", "??", "??",
}

DOMAIN_BONUS = 1.5
TAG_BONUS = 1.0


def _ensure_dir():
    WORD_MAP_DIR.mkdir(parents=True, exist_ok=True)


def _tokens(text: str) -> List[str]:
    text = text or ""
    raw = re.findall(r"[\u4e00-\u9fff]{2,}|[A-Za-z][A-Za-z0-9_\-]{2,}", text.lower())
    result = []
    for token in raw:
        token = token.strip("_-")
        if not token or token in STOPWORDS:
            continue
        if token.startswith("mem_") or token.startswith("profile_candidate_") or token.startswith("moment_"):
            continue
        if re.fullmatch(r"[0-9_\-]+", token):
            continue
        if len(token) > 24:
            token = token[:24]
        result.append(token)
    return result


def _source_text(memory) -> str:
    tags = " ".join(memory.tags) if memory.tags else ""
    return f"{memory.name} {memory.domain} {tags} {memory.content}"


def _add_source(nodes: Dict[str, Dict], token: str, source_id: str, source_type: str, weight: float):
    node = nodes.setdefault(token, {
        "word": token,
        "weight": 0.0,
        "bucket_count": 0,
        "moment_count": 0,
        "sources": [],
        "source_types": {},
    })
    node["weight"] += weight
    if source_type == "bucket":
        node["bucket_count"] += 1
    if source_type == "moment":
        node["moment_count"] += 1
    if len(node["sources"]) < 8 and source_id not in node["sources"]:
        node["sources"].append(source_id)
    node["source_types"][source_type] = node["source_types"].get(source_type, 0) + 1


def rebuild_word_map(max_tokens_per_source: int = 40) -> Dict:
    _ensure_dir()
    nodes: Dict[str, Dict] = {}
    edge_counter = Counter()
    edge_sources = defaultdict(list)

    memories = memory_system.load_all_memories(include_archive=False)
    for memory in memories:
        tokens = _tokens(_source_text(memory))[:max_tokens_per_source]
        unique = list(dict.fromkeys(tokens))
        weight = 1.0 + (TAG_BONUS if memory.tags else 0.0) + (DOMAIN_BONUS if memory.domain else 0.0)
        for token in unique:
            _add_source(nodes, token, memory.id, "bucket", weight)
        for a, b in combinations(sorted(unique[:18]), 2):
            edge = (a, b)
            edge_counter[edge] += 1
            if len(edge_sources[edge]) < 6:
                edge_sources[edge].append(memory.id)

    for moment in list_moments():
        moment_id = moment.get("id", "")
        text = f"{moment.get('title', '')} {' '.join(moment.get('tags', []))} {moment.get('content', '')}"
        tokens = _tokens(text)[:max_tokens_per_source]
        unique = list(dict.fromkeys(tokens))
        for token in unique:
            _add_source(nodes, token, moment_id, "moment", 0.8)
        for a, b in combinations(sorted(unique[:14]), 2):
            edge = (a, b)
            edge_counter[edge] += 1
            if len(edge_sources[edge]) < 6:
                edge_sources[edge].append(moment_id)

    node_list = []
    for node in nodes.values():
        edge_degree = sum(1 for edge in edge_counter if node["word"] in edge)
        concept_score = node["weight"] + node["bucket_count"] * 2 + node["moment_count"] + edge_degree * 0.4
        node_list.append({
            "word": node["word"],
            "weight": round(node["weight"], 3),
            "concept_score": round(concept_score, 3),
            "bucket_count": node["bucket_count"],
            "moment_count": node["moment_count"],
            "sources": node["sources"],
        })

    node_list.sort(key=lambda item: item["concept_score"], reverse=True)

    edges = []
    for (source, target), count in edge_counter.most_common(200):
        edges.append({
            "source": source,
            "target": target,
            "weight": count,
            "sample_ids": edge_sources[(source, target)],
        })

    result = {
        "generated_at": datetime.now().isoformat(),
        "note": "Word Map Lite is observational. It is not high-confidence evidence.",
        "node_count": len(node_list),
        "edge_count": len(edges),
        "top_concepts": node_list[:40],
        "nodes": node_list[:300],
        "edges": edges,
    }
    WORD_MAP_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def load_word_map() -> Dict:
    if not WORD_MAP_PATH.exists():
        return rebuild_word_map()
    try:
        return json.loads(WORD_MAP_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return rebuild_word_map()


def weak_concept_hints(query: str, max_items: int = 5) -> Dict:
    """Return weak concept overlap. This is not evidence and must not bypass recall filters."""
    word_map = load_word_map()
    query_tokens = set(_tokens(query))
    if not query_tokens:
        return {"used": False, "note": "No concept overlap.", "concepts": []}
    concepts = []
    for node in word_map.get("nodes", []):
        word = node.get("word")
        if word in query_tokens:
            concepts.append({
                "word": word,
                "score": node.get("concept_score", 0),
                "sample_ids": node.get("sources", [])[:4],
                "confidence": "weak_concept_hint",
            })
        if len(concepts) >= max_items:
            break
    return {
        "used": bool(concepts),
        "note": "Word Map Lite is a weak navigation hint, not evidence.",
        "concepts": concepts,
    }


def render_weak_concept_hints(hints: Dict) -> str:
    concepts = hints.get("concepts", []) if hints else []
    if not concepts:
        return "(none)"
    return "\n".join(
        f"- concept: {item.get('word')} | confidence: weak | sample_ids: {', '.join(item.get('sample_ids', []))}"
        for item in concepts
    )
