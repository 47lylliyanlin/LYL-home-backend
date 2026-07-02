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
- If you need memory, reply with exactly one compact JSON object and no other text:
{"tool":"memory_breath","query":"short search query","reason":"why this memory search is needed"}
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
    if payload.get("tool") != "memory_breath":
        return None
    query = str(payload.get("query") or "").strip()
    if not query:
        return None
    reason = str(payload.get("reason") or "").strip()
    return {
        "tool": "memory_breath",
        "query": query[:240],
        "reason": reason[:300],
    }


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


def run_memory_tool(request: Dict) -> Dict:
    if request.get("tool") != "memory_breath":
        return {"tool": request.get("tool"), "error": "unsupported tool"}
    return memory_breath(query=request.get("query", ""), top_k=3)


def render_tool_result_for_prompt(result: Dict) -> str:
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
