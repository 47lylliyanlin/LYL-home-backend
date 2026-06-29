"""
Automatic memory extraction from each conversation.
"""

import json
from typing import Dict, List, Optional
from .memory import memory_system
from .ai_client import json_completion


async def extract_memory_from_conversation(
    user_message: str,
    assistant_message: str,
    conversation_history: List[Dict] = None
) -> Optional[Dict]:
    """Extract one memory candidate from the latest conversation turn."""

    history_text = ""
    if conversation_history:
        recent = conversation_history[-6:]
        history_text = "\n".join(
            f"{item.get('role', '')}: {item.get('content', '')}" for item in recent
        )

    prompt = f"""Analyze this conversation and decide whether there is something I should remember.

Recent context:
{history_text or '(none)'}

Current turn:
User said: {user_message}
I replied: {assistant_message}

Memory types:
1. permanent - stable long-term facts, relationship definitions, important preferences, commitments.
2. dynamic - recent events, project progress, temporary plans, unresolved topics.
3. feel - my emotional reflection or an important emotional moment from this conversation.
4. plan - a concrete task or next action I should continue later.
5. letter - a long message or letter that should be preserved as original text.

Remember only if the information is useful for future conversations, specific enough to reuse, and unlikely to create a false assumption.

Return exactly this JSON shape:
{{
    "should_remember": true/false,
    "name": "short title, 3-10 words",
    "domain": "relationship/project/preference/plan/feeling/etc",
    "content": "first-person memory content, 1-3 concise sentences",
    "importance": 1-10,
    "valence": 0.0-1.0,
    "arousal": 0.0-1.0,
    "tags": ["tag1", "tag2"],
    "type": "permanent/dynamic/feel/plan/letter",
    "reason": "why this is worth remembering"
}}

If nothing should be remembered, return {{"should_remember": false}}.
Return JSON only. Do not use markdown fences. Do not explain.
"""

    try:
        return json_completion(
            system_prompt="Return valid JSON only. Do not use markdown fences.",
            user_message=prompt,
            max_tokens=1024,
        )

    except Exception as e:
        print(f"Memory extraction failed: {e}")
        return None


async def save_extracted_memory(extraction: Dict):
    """Save an extracted memory candidate."""
    if not extraction or not extraction.get('should_remember'):
        return

    memory = memory_system.create_memory(
        content=extraction['content'],
        importance=extraction.get('importance', 5),
        mem_type=extraction.get('type', 'dynamic'),
        tags=extraction.get('tags', []),
        valence=extraction.get('valence', 0.5),
        arousal=extraction.get('arousal', 0.5),
        name=extraction.get('name', ''),
        domain=extraction.get('domain', '')
    )

    print(f"Saved memory: {memory.id} - {extraction['content'][:50]}...")
    return memory
