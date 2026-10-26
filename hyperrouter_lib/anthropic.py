"""Anthropic Messages <-> OpenAI chat conversions (pure functions)."""

from __future__ import annotations

import json
import uuid
from typing import Any

from .text import content_to_text


def response_message(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        return {}
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        return {}
    message = choices[0].get("message")
    return message if isinstance(message, dict) else {}


def _anthropic_blocks_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = [str(block.get("text") or "") for block in content
                 if isinstance(block, dict) and block.get("type") == "text"]
        return "\n".join(parts)
    return ""


def _anthropic_tool_result_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(str(block.get("text") or ""))
            elif isinstance(block, dict) and block.get("type") == "image":
                parts.append("[image]")
        return "\n".join(parts)
    return str(content or "")


def anthropic_to_openai(body: dict[str, Any]) -> tuple[list[dict[str, Any]],
                                                       list[dict[str, Any]]]:
    """Convert an Anthropic Messages request into OpenAI chat messages + tools."""
    messages: list[dict[str, Any]] = []
    system = body.get("system")
    system_text = _anthropic_blocks_text(system)
    if system_text.strip():
        messages.append({"role": "system", "content": system_text})
    for raw in body.get("messages") or []:
        if not isinstance(raw, dict):
            continue
        role = str(raw.get("role") or "user")
        content = raw.get("content")
        if isinstance(content, str):
            messages.append({"role": role, "content": content})
            continue
        if not isinstance(content, list):
            continue
        texts: list[str] = []
        tool_calls: list[dict[str, Any]] = []
        tool_results: list[tuple[str, str]] = []
        images: list[dict[str, Any]] = []
        for block in content:
            if not isinstance(block, dict):
                continue
            kind = block.get("type")
            if kind == "text":
                texts.append(str(block.get("text") or ""))
            elif kind == "image":
                source = block.get("source") or {}
                if isinstance(source, dict):
                    if source.get("type") == "base64":
                        media = str(source.get("media_type") or "image/png")
                        data = str(source.get("data") or "")
                        images.append({"type": "image_url",
                                       "image_url": {"url": f"data:{media};base64,{data}"}})
                    elif source.get("type") == "url" and source.get("url"):
                        images.append({"type": "image_url",
                                       "image_url": {"url": str(source["url"])}})
            elif kind == "tool_use":
                tool_calls.append({
                    "id": str(block.get("id") or f"call_{len(tool_calls)}"),
                    "type": "function",
                    "function": {"name": str(block.get("name") or ""),
                                 "arguments": json.dumps(block.get("input") or {})},
                })
            elif kind == "tool_result":
                tool_results.append((str(block.get("tool_use_id") or ""),
                                     _anthropic_tool_result_text(block.get("content"))))
        text = "\n".join(part for part in texts if part)
        if role == "assistant":
            message: dict[str, Any] = {"role": "assistant", "content": text}
            if tool_calls:
                message["tool_calls"] = tool_calls
            messages.append(message)
            continue
        if text or images:
            if images:
                parts = ([{"type": "text", "text": text}] if text else []) + images
                messages.append({"role": role, "content": parts})
            else:
                messages.append({"role": role, "content": text})
        for tool_id, output in tool_results:
            messages.append({"role": "tool", "tool_call_id": tool_id,
                             "content": output or "(empty)"})
    tools: list[dict[str, Any]] = []
    for tool in body.get("tools") or []:
        if not isinstance(tool, dict):
            continue
        schema = tool.get("input_schema")
        if not isinstance(schema, dict):
            schema = {"type": "object", "properties": {}}
        tools.append({"type": "function", "function": {
            "name": str(tool.get("name") or ""),
            "description": str(tool.get("description") or "")[:1000],
            "parameters": schema,
        }})
    return messages, tools


def openai_response_to_anthropic(result: dict[str, Any], model: str) -> dict[str, Any]:
    """Convert an OpenAI chat completion into an Anthropic Messages response."""
    message = response_message(result)
    content: list[dict[str, Any]] = []
    text = content_to_text(message.get("content"))
    if text:
        content.append({"type": "text", "text": text})
    calls = message.get("tool_calls") or []
    for index, call in enumerate(calls):
        if not isinstance(call, dict):
            continue
        function = call.get("function") or {}
        raw = function.get("arguments")
        try:
            parsed = json.loads(raw) if isinstance(raw, str) and raw.strip() else (raw or {})
        except json.JSONDecodeError:
            parsed = {"input": raw}
        content.append({"type": "tool_use", "id": str(call.get("id") or f"toolu_{index}"),
                        "name": str(function.get("name") or ""),
                        "input": parsed if isinstance(parsed, dict) else {}})
    usage = result.get("usage") or {}
    return {
        "id": f"msg_{uuid.uuid4().hex[:24]}",
        "type": "message",
        "role": "assistant",
        "model": model,
        "content": content,
        "stop_reason": "tool_use" if calls else "end_turn",
        "stop_sequence": None,
        "usage": {"input_tokens": int(usage.get("prompt_tokens") or 0),
                  "output_tokens": int(usage.get("completion_tokens") or 0)},
    }
