"""LLM backend: raw HTTP to a local Ollama server (no SDK, no agent framework)."""
from __future__ import annotations

import json
import os

import requests

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen3:8b")
NUM_CTX = int(os.environ.get("OLLAMA_NUM_CTX", "16384"))
THINK = os.environ.get("OLLAMA_THINK", "1") == "1"  # qwen3 reasoning mode; ignored by models without it
MAX_TOKENS = int(os.environ.get("OLLAMA_MAX_TOKENS", "3072"))  # caps runaway reasoning so a turn cannot hang
TIMEOUT = int(os.environ.get("OLLAMA_TIMEOUT", "240"))


class OllamaBackend:
    def __init__(self, model: str = OLLAMA_MODEL, think: bool = THINK) -> None:
        self.model = model
        self.think = think
        self.calls = 0  # LLM calls (not tool calls)

    def chat(self, messages: list[dict], tools: list[dict] | None = None, json_schema: dict | None = None) -> dict:
        """One chat turn. Returns {"content": str, "tool_calls": [{"name", "args"}], "message": raw assistant msg}."""
        body = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": 0, "num_ctx": NUM_CTX, "num_predict": MAX_TOKENS},
            "keep_alive": "30m",
        }
        if tools:
            body["tools"] = tools
        if json_schema:
            body["format"] = json_schema
        if self.think and "qwen3" in self.model:
            body["think"] = True
        r = requests.post(f"{OLLAMA_URL}/api/chat", json=body, timeout=TIMEOUT)
        if r.status_code != 200 and "think" in body:  # older server / model without thinking support
            body.pop("think")
            r = requests.post(f"{OLLAMA_URL}/api/chat", json=body, timeout=TIMEOUT)
        r.raise_for_status()
        self.calls += 1
        msg = r.json()["message"]
        calls = []
        for tc in msg.get("tool_calls") or []:
            fn = tc.get("function", {})
            args = fn.get("arguments") or {}
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    args = {}
            calls.append({"name": fn.get("name", ""), "args": args})
        return {"content": msg.get("content") or "", "tool_calls": calls, "message": msg}


def tool_schema(name: str, description: str, properties: dict, required: list[str]) -> dict:
    return {"type": "function", "function": {"name": name, "description": description,
                                             "parameters": {"type": "object", "properties": properties, "required": required}}}
