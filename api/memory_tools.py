"""
Internal memory tools for Kiro Gateway.

This is not the MCP server layer. It is a small Gateway-side tool loop so Web,
PWA, and App clients can let the model decide when to search memory.
"""

import json
import os
from typing import Dict, List, Optional

from .bucket_format import direct_seed_text
from .memory import Memory, memory_system
from .memory_candidates import create_memory_candidate
from .memory_graph import list_edges, list_moments


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _truncate(text: str, limit: int = 700) -> str:
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "..."


def internal_tool_loop_enabled() -> bool:
    return _env_bool("MEMORY_INTERNAL_TOOL_LOOP_ENABLED", True)


def internal_tool_instructions() -> str:
    if not internal_tool_loop_enabled():
        return ""
    return """

Internal memory tool option:
- You may decide whether long-term memory is needed before answering.
- Use this only when the current message truly needs long-term memory that is not already present in the context.
- Do not use it for just-now / previous sentence / current-session questions; those are handled by recent chat context.
- If you need to search memory, reply with exactly one compact JSON object and no other text:
{"tool":"memory_breath","query":"short search query","reason":"why this memory search is needed"}
- If the relevant memory id is already available and the user asks to expand it, reply with exactly:
{"tool":"memory_read_bucket","bucket_id":"mem_xxx","reason":"why this bucket detail is needed"}
- If the user asks what happened around a surfaced memory, how it connects, or what followed, reply with exactly:
{"tool":"memory_trace","id":"mem_or_moment_id","reason":"why graph context is needed"}
- You may propose a pending memory candidate only when the user explicitly asks you to remember something, or when a stable fact, promise, project state, or relationship milestone clearly changed. Use it sparingly. Do not store guesses about the user as facts.
- To propose a pending memory candidate, reply with exactly:
{"tool":"memory_hold_candidate","title":"short title","content":"what should be remembered","suggested_type":"dynamic","reason":"why it may be worth remembering"}
- If you do not need memory, answer normally.
"""


def _strip_code_fence(text: str) -> str:
    value = (text or "").strip()
    if value.startswith("```"):
        value = value.strip("`").strip()
        if value.lower().startswith("json"):
            value = value[4:].strip()
    return value


def parse_tool_request(raw_text: str) -> Optional[Dict]:
    value = _strip_code_fence(raw_text)
    if not value.startswith("{") or not value.endswith("}"):
        return None
    try:
        payload = json.loads(value)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None

    tool = payload.get("tool")
    reason = str(payload.get("reason") or "").strip()[:300]
    if tool == "memory_breath":
        query = str(payload.get("query") or "").strip()
        if not query:
            return None
        return {
            "tool": "memory_breath",
            "query": query[:240],
            "reason": reason,
        }

    if tool == "memory_read_bucket":
        bucket_id = str(payload.get("bucket_id") or payload.get("id") or "").strip()
        if not bucket_id:
            return None
        return {
            "tool": "memory_read_bucket",
            "bucket_id": bucket_id[:120],
            "reason": reason,
        }

    if tool == "memory_trace":
        trace_id = str(payload.get("id") or payload.get("bucket_id") or payload.get("moment_id") or "").strip()
        if not trace_id:
            return None
        return {
            "tool": "memory_trace",
            "id": trace_id[:140],
            "reason": reason,
        }

    if tool == "memory_hold_candidate":
        title = str(payload.get("title") or "").strip()
        content = str(payload.get("content") or payload.get("memory") or "").strip()
        if not content:
            return None
        evidence_ids = payload.get("evidence_ids") or []
        if not isinstance(evidence_ids, list):
            evidence_ids = []
        return {
            "tool": "memory_hold_candidate",
            "title": title[:120] or "Untitled memory candidate",
            "content": content[:4000],
            "suggested_type": str(payload.get("suggested_type") or "dynamic").strip()[:80],
            "reason": reason or str(payload.get("why") or "").strip()[:300],
            "evidence_ids": [str(item).strip()[:160] for item in evidence_ids if str(item).strip()][:8],
        }

    return None


def _memory_item(memory: Memory, item: Dict, content_limit: int) -> Dict:
    return {
        "id": memory.id,
        "title": memory.name or memory.id,
        "type": memory.type,
        "tags": memory.tags,
        "importance": memory.importance,
        "use_count": memory.use_count,
        "keyword_score": item.get("keyword_score"),
        "vector_score": item.get("vector_score"),
        "base_score": item.get("base_score"),
        "final_score": item.get("final_score"),
        "content": _truncate(direct_seed_text(memory.content), content_limit),
    }


def memory_breath(query: str, top_k: int = 3, content_limit: int = 650) -> Dict:
    """Search active long-term memories without touching use_count."""
    top_k = min(max(int(top_k or 3), 1), 5)
    explained = memory_system.explain_search_memories(query=query, top_k=top_k)
    memories: List[Dict] = []
    for item in explained:
        memory = item.get("memory")
        if not memory:
            continue
        memories.append(_memory_item(memory, item, content_limit))
    return {
        "tool": "memory_breath",
        "query": query,
        "count": len(memories),
        "memories": memories,
    }


def _find_active_memory(memory_id: str) -> Optional[Memory]:
    for memory in memory_system.load_all_memories(include_archive=False):
        if memory.id == memory_id:
            return memory
    return None


def memory_read_bucket(bucket_id: str, content_limit: int = 2200) -> Dict:
    """Read one active memory bucket without touching use_count."""
    memory = _find_active_memory(bucket_id)
    if not memory:
        return {
            "tool": "memory_read_bucket",
            "bucket_id": bucket_id,
            "found": False,
            "error": "active bucket not found",
        }
    return {
        "tool": "memory_read_bucket",
        "bucket_id": bucket_id,
        "found": True,
        "memory": {
            "id": memory.id,
            "title": memory.name or memory.id,
            "type": memory.type,
            "tags": memory.tags,
            "importance": memory.importance,
            "use_count": memory.use_count,
            "content": _truncate(direct_seed_text(memory.content), content_limit),
        },
    }


def _moment_item(moment: Dict, content_limit: int = 700) -> Dict:
    return {
        "id": moment.get("id"),
        "bucket_id": moment.get("bucket_id"),
        "title": moment.get("title") or moment.get("id"),
        "tags": moment.get("tags", []),
        "created_at": moment.get("created_at"),
        "content": _truncate(moment.get("content", ""), content_limit),
    }


def _edge_item(edge: Dict) -> Dict:
    return {
        "id": edge.get("id"),
        "source_id": edge.get("source_id"),
        "target_id": edge.get("target_id"),
        "type": edge.get("type"),
        "note": edge.get("note", ""),
        "created_at": edge.get("created_at"),
    }


def memory_trace(trace_id: str, max_moments: int = 5, max_edges: int = 8) -> Dict:
    """Trace graph context around an active bucket or moment without mutation."""
    active_memory = _find_active_memory(trace_id)
    all_moments = list_moments()
    moments_by_id = {item.get("id"): item for item in all_moments}
    target_moment = moments_by_id.get(trace_id)

    related_moments: List[Dict] = []
    if active_memory:
        related_moments.extend(list_moments(bucket_id=trace_id))
    elif target_moment:
        related_moments.append(target_moment)
        bucket_id = target_moment.get("bucket_id")
        if bucket_id:
            related_moments.extend(item for item in list_moments(bucket_id=bucket_id) if item.get("id") != trace_id)

    related_edges = []
    seen_edges = set()
    for edge in list_edges():
        source = edge.get("source_id")
        target = edge.get("target_id")
        if source == trace_id or target == trace_id:
            related_edges.append(edge)
            seen_edges.add(edge.get("id"))
            continue
        if active_memory and (source == active_memory.id or target == active_memory.id):
            related_edges.append(edge)
            seen_edges.add(edge.get("id"))
            continue
        if target_moment and (source == target_moment.get("bucket_id") or target == target_moment.get("bucket_id")):
            related_edges.append(edge)
            seen_edges.add(edge.get("id"))

    related_moments = related_moments[:max_moments]
    related_edges = related_edges[:max_edges]

    return {
        "tool": "memory_trace",
        "id": trace_id,
        "found": bool(active_memory or target_moment or related_moments or related_edges),
        "target": {
            "kind": "bucket" if active_memory else "moment" if target_moment else "unknown",
            "id": trace_id,
            "title": (active_memory.name if active_memory else target_moment.get("title") if target_moment else trace_id),
            "type": active_memory.type if active_memory else None,
        },
        "moments": [_moment_item(item) for item in related_moments],
        "edges": [_edge_item(item) for item in related_edges],
        "count": len(related_moments) + len(related_edges),
    }


def run_memory_tool(request: Dict) -> Dict:
    if request.get("tool") == "memory_breath":
        return memory_breath(query=request.get("query", ""), top_k=3)
    if request.get("tool") == "memory_read_bucket":
        return memory_read_bucket(bucket_id=request.get("bucket_id", ""))
    if request.get("tool") == "memory_trace":
        return memory_trace(trace_id=request.get("id", ""))
    if request.get("tool") == "memory_hold_candidate":
        return {
            "tool": "memory_hold_candidate",
            **create_memory_candidate(
                title=request.get("title", ""),
                content=request.get("content", ""),
                suggested_type=request.get("suggested_type", "dynamic"),
                reason=request.get("reason", ""),
                source="internal_tool",
                evidence_ids=request.get("evidence_ids", []),
                confidence=0.5,
            ),
        }
    return {"tool": request.get("tool"), "error": "unsupported tool"}


def render_tool_result_for_prompt(result: Dict) -> str:
    tool = result.get("tool")
    if tool == "memory_hold_candidate":
        candidate = result.get("candidate") or {}
        gate = result.get("gate") or {}
        if not candidate:
            return f"memory_hold_candidate failed: {result.get('error', 'unknown error')}"
        if not result.get("ok"):
            return "\n".join([
                "Internal memory tool result: memory_hold_candidate",
                "The write gate did not accept this as pending long-term memory. A review record may exist, but it is not a pending memory.",
                "In the final answer, do not claim this was remembered or saved. Continue naturally.",
                f"- candidate_id: {candidate.get('id')}",
                f"  title: {candidate.get('title')}",
                f"  status: {candidate.get('status')}",
                f"  gate_code: {gate.get('code') or candidate.get('gate_code')}",
                f"  gate_reason: {gate.get('reason') or candidate.get('gate_reason')}",
            ])
        return "\n".join([
            "Internal memory tool result: memory_hold_candidate",
            "A pending memory candidate was created for later review. It is not confirmed long-term memory yet.",
            "In the final answer, acknowledge naturally if appropriate, but do not say it has been permanently saved.",
            f"- candidate_id: {candidate.get('id')}",
            f"  title: {candidate.get('title')}",
            f"  suggested_type: {candidate.get('suggested_type')}",
            f"  status: {candidate.get('status')}",
            f"  gate_code: {gate.get('code') or candidate.get('gate_code')}",
        ])

    if tool == "memory_read_bucket":
        if not result.get("found"):
            return f"memory_read_bucket did not find active bucket: {result.get('bucket_id', '')}"
        item = result.get("memory") or {}
        tags = ", ".join(item.get("tags") or []) or "none"
        return "\n".join([
            "Internal memory tool result: memory_read_bucket",
            "Use this bucket detail as optional background. Do not mention the tool unless the user asks.",
            f"- id: {item.get('id')}",
            f"  title: {item.get('title')}",
            f"  type: {item.get('type')}",
            f"  tags: {tags}",
            f"  content: {item.get('content')}",
        ])

    if tool == "memory_trace":
        if not result.get("found"):
            return f"memory_trace found no graph context for id: {result.get('id', '')}"
        lines = [
            "Internal memory tool result: memory_trace",
            "Use this graph context as optional background. Treat it as supporting context, not proof by itself.",
            f"target: {result.get('target', {}).get('kind')} {result.get('id')}",
        ]
        if result.get("moments"):
            lines.append("moments:")
            for item in result.get("moments", []):
                lines.append(
                    "\n".join([
                        f"- moment_id: {item.get('id')}",
                        f"  bucket_id: {item.get('bucket_id')}",
                        f"  title: {item.get('title')}",
                        f"  preview: {item.get('content')}",
                    ])
                )
        if result.get("edges"):
            lines.append("edges:")
            for item in result.get("edges", []):
                lines.append(
                    f"- edge_id: {item.get('id')} | {item.get('source_id')} --{item.get('type')}--> {item.get('target_id')} | {item.get('note')}"
                )
        return "\n".join(lines)

    memories = result.get("memories") or []
    if not memories:
        return f"memory_breath found no active long-term memories for query: {result.get('query', '')}"
    lines = [
        "Internal memory tool result: memory_breath",
        f"query: {result.get('query', '')}",
        "Use these as optional background. Do not mention the tool unless the user asks.",
    ]
    for item in memories:
        tags = ", ".join(item.get("tags") or []) or "none"
        lines.append(
            "\n".join([
                f"- id: {item.get('id')}",
                f"  title: {item.get('title')}",
                f"  type: {item.get('type')}",
                f"  tags: {tags}",
                f"  score: keyword={item.get('keyword_score')} vector={item.get('vector_score')} final={item.get('final_score')}",
                f"  content: {item.get('content')}",
            ])
        )
    return "\n".join(lines)


def tool_result_summary(result: Dict) -> Dict:
    if result.get("tool") == "memory_hold_candidate":
        candidate = result.get("candidate") or {}
        gate = result.get("gate") or {}
        return {
            "tool": result.get("tool"),
            "ok": result.get("ok", False),
            "error": result.get("error"),
            "gate": {
                "decision": gate.get("decision") or candidate.get("gate_decision"),
                "code": gate.get("code") or candidate.get("gate_code"),
                "reason": gate.get("reason") or candidate.get("gate_reason"),
                "duplicate": gate.get("duplicate") or candidate.get("gate_duplicate"),
            },
            "candidate": {
                "id": candidate.get("id"),
                "title": candidate.get("title"),
                "suggested_type": candidate.get("suggested_type"),
                "status": candidate.get("status"),
                "gate_code": candidate.get("gate_code"),
            } if candidate else None,
            "memories": [],
            "count": 1 if candidate else 0,
        }
    if result.get("tool") == "memory_read_bucket":
        memory = result.get("memory") or {}
        return {
            "tool": result.get("tool"),
            "bucket_id": result.get("bucket_id"),
            "found": result.get("found", False),
            "count": 1 if result.get("found") else 0,
            "memories": [{
                "id": memory.get("id"),
                "title": memory.get("title"),
                "type": memory.get("type"),
            }] if result.get("found") else [],
        }
    if result.get("tool") == "memory_trace":
        return {
            "tool": result.get("tool"),
            "id": result.get("id"),
            "found": result.get("found", False),
            "count": result.get("count", 0),
            "target": result.get("target"),
            "moments": [
                {
                    "id": item.get("id"),
                    "bucket_id": item.get("bucket_id"),
                    "title": item.get("title"),
                }
                for item in result.get("moments", [])
            ],
            "edges": [
                {
                    "id": item.get("id"),
                    "source_id": item.get("source_id"),
                    "target_id": item.get("target_id"),
                    "type": item.get("type"),
                }
                for item in result.get("edges", [])
            ],
            "memories": [],
        }
    return {
        "tool": result.get("tool"),
        "query": result.get("query"),
        "count": result.get("count", 0),
        "memories": [
            {
                "id": item.get("id"),
                "title": item.get("title"),
                "type": item.get("type"),
                "keyword_score": item.get("keyword_score"),
                "vector_score": item.get("vector_score"),
                "final_score": item.get("final_score"),
            }
            for item in result.get("memories", [])
        ],
    }
