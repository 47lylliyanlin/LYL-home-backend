"""
Unified AI client for chat and memory extraction.

Provider switching is controlled by environment variables. The common case for
proxy services is OpenAI-compatible Chat Completions, even when the upstream
model is GPT, Claude, or Gemini.
"""

import json
import os
import urllib.error
import urllib.request
from typing import Dict, List, Optional

import anthropic


def _load_dotenv_once():
    env_path = os.getenv("KIRO_ENV_FILE", ".env")
    if not os.path.exists(env_path):
        return
    try:
        with open(env_path, "r", encoding="utf-8") as f:
            for raw_line in f:
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip("'").strip('\"')
                if key and key not in os.environ:
                    os.environ[key] = value
    except OSError:
        return


_load_dotenv_once()


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def _active_profile() -> str:
    return _env("AI_ACTIVE_PROFILE", _env("AI_PROVIDER", "anthropic")).upper().replace("-", "_")


def _profile_env(key: str, default: str = "") -> str:
    profile = _active_profile()
    return _env(f"AI_{profile}_{key}", _env(f"AI_{key}", default))


def active_ai_config() -> Dict[str, str]:
    profile = _active_profile()
    provider = _profile_env("PROVIDER", profile.lower())
    return {
        "profile": profile.lower(),
        "provider": provider.lower(),
        "base_url": _profile_env("BASE_URL"),
        "model": _profile_env("MODEL"),
        "has_api_key": bool(_profile_env("API_KEY")),
    }


def _anthropic_text(response) -> str:
    text = ""
    for block in getattr(response, "content", []) or []:
        if hasattr(block, "text"):
            text += block.text
    return text


def _openai_chat_text(payload: Dict) -> str:
    choices = payload.get("choices") or []
    if not choices:
        return ""
    message = choices[0].get("message") or {}
    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict):
                parts.append(item.get("text") or item.get("content") or "")
        return "".join(parts)
    return ""


def _clean_messages(messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
    cleaned = []
    for item in messages or []:
        role = item.get("role")
        content = (item.get("content") or "").strip()
        if role in {"user", "assistant"} and content:
            cleaned.append({"role": role, "content": content})
    return cleaned


def _chat_with_anthropic_messages(system_prompt: str, messages: List[Dict[str, str]], max_tokens: int) -> str:
    api_key = _profile_env("API_KEY", _env("ANTHROPIC_API_KEY"))
    base_url = _profile_env("BASE_URL", _env("ANTHROPIC_BASE_URL", "https://api.anthropic.com"))
    model = _profile_env("MODEL", _env("ANTHROPIC_MODEL", "claude-opus-4-6"))
    client = anthropic.Anthropic(api_key=api_key, base_url=base_url)
    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system_prompt or "",
        messages=_clean_messages(messages),
    )
    return _anthropic_text(response)


def _chat_with_anthropic(system_prompt: str, user_message: str, max_tokens: int) -> str:
    return _chat_with_anthropic_messages(system_prompt, [{"role": "user", "content": user_message}], max_tokens)


def _chat_with_openai_compatible_messages(system_prompt: str, messages: List[Dict[str, str]], max_tokens: int) -> str:
    api_key = _profile_env("API_KEY", _env("OPENAI_API_KEY"))
    base_url = _profile_env("BASE_URL", _env("OPENAI_BASE_URL", "https://api.openai.com/v1"))
    model = _profile_env("MODEL", _env("OPENAI_MODEL", "gpt-4.1"))
    url = base_url.rstrip("/") + "/chat/completions"
    payload_messages: List[Dict[str, str]] = []
    if system_prompt:
        payload_messages.append({"role": "system", "content": system_prompt})
    payload_messages.extend(_clean_messages(messages))
    body = json.dumps({
        "model": model,
        "messages": payload_messages,
        "max_tokens": max_tokens,
    }).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            payload = json.loads(response.read().decode("utf-8"))
            return _openai_chat_text(payload)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"OpenAI-compatible API failed: {exc.code} {detail}") from exc


def _chat_with_openai_compatible(system_prompt: str, user_message: str, max_tokens: int) -> str:
    return _chat_with_openai_compatible_messages(system_prompt, [{"role": "user", "content": user_message}], max_tokens)


def _gemini_text(payload: Dict) -> str:
    parts = []
    for candidate in payload.get("candidates", []) or []:
        content = candidate.get("content") or {}
        for part in content.get("parts", []) or []:
            if isinstance(part, dict) and isinstance(part.get("text"), str):
                parts.append(part["text"])
    return "".join(parts)


def _gemini_contents(messages: List[Dict[str, str]]) -> List[Dict]:
    contents = []
    for item in _clean_messages(messages):
        role = "model" if item["role"] == "assistant" else "user"
        contents.append({"role": role, "parts": [{"text": item["content"]}]})
    return contents


def _chat_with_gemini_native_messages(system_prompt: str, messages: List[Dict[str, str]], max_tokens: int) -> str:
    api_key = _profile_env("API_KEY", _env("GEMINI_API_KEY"))
    base_url = _profile_env("BASE_URL", _env("GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta"))
    model = _profile_env("MODEL", _env("GEMINI_MODEL", "gemini-2.5-pro"))
    model_path = model if model.startswith("models/") else f"models/{model}"
    url = base_url.rstrip("/") + f"/{model_path}:generateContent?key={api_key}"
    payload = {
        "contents": _gemini_contents(messages),
        "generationConfig": {
            "maxOutputTokens": max_tokens,
        },
    }
    if system_prompt:
        payload["systemInstruction"] = {
            "parts": [{"text": system_prompt}],
        }
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            response_payload = json.loads(response.read().decode("utf-8"))
            return _gemini_text(response_payload)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Gemini native API failed: {exc.code} {detail}") from exc


def _chat_with_gemini_native(system_prompt: str, user_message: str, max_tokens: int) -> str:
    return _chat_with_gemini_native_messages(system_prompt, [{"role": "user", "content": user_message}], max_tokens)


def chat_messages(system_prompt: str, messages: List[Dict[str, str]], max_tokens: int = 1024) -> str:
    provider = active_ai_config()["provider"]
    if provider in {"anthropic", "claude"}:
        return _chat_with_anthropic_messages(system_prompt, messages, max_tokens)
    if provider in {"gemini_native", "google_gemini", "google"}:
        return _chat_with_gemini_native_messages(system_prompt, messages, max_tokens)
    if provider in {"openai", "gpt", "gemini", "openai_compatible", "proxy"}:
        return _chat_with_openai_compatible_messages(system_prompt, messages, max_tokens)
    raise ValueError(f"Unsupported AI provider: {provider}")


def chat_completion(system_prompt: str, user_message: str, max_tokens: int = 1024) -> str:
    return chat_messages(system_prompt, [{"role": "user", "content": user_message}], max_tokens=max_tokens)


def json_completion(system_prompt: str, user_message: str, max_tokens: int = 1024) -> Optional[Dict]:
    raw_text = chat_completion(system_prompt, user_message, max_tokens=max_tokens).strip()
    if raw_text.startswith("```"):
        raw_text = raw_text.strip("`").strip()
        raw_text = raw_text.removeprefix("json").removeprefix("JSON").strip()
    return json.loads(raw_text)
