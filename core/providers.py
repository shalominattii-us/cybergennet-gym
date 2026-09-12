"""
Model provider adapters — local-first, pluggable.

Supports Venice (OpenAI-compatible), Ollama (local), and a deterministic
fallback. Add new providers by implementing the ModelProvider interface.
"""
from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod
from typing import Optional

import httpx


class ModelProvider(ABC):
    """Abstract interface for model providers."""

    @abstractmethod
    async def chat(self, messages: list[dict], **kwargs) -> str:
        ...

    @abstractmethod
    async def evaluate(
        self, prompt: str, context: dict, rubric: dict
    ) -> dict:
        """Evaluate something against a rubric. Returns score + reasoning."""
        ...


class VeniceProvider(ModelProvider):
    """Venice AI provider — OpenAI-compatible API."""

    def __init__(self):
        self.api_key = os.environ.get("VENICE_API_KEY", "")
        self.base_url = "https://api.venice.ai/api/v1"
        self.model = "venice-uncensored"

    async def chat(self, messages: list[dict], **kwargs) -> str:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": kwargs.get("model", self.model),
                    "messages": messages,
                    "temperature": kwargs.get("temperature", 0.7),
                    "max_tokens": kwargs.get("max_tokens", 1024),
                    "extra_body": {
                        "venice_parameters": {
                            "enable_web_search": kwargs.get("web_search", "auto"),
                        }
                    } if kwargs.get("web_search") else None,
                },
                timeout=60,
            )
            data = resp.json()
            return data["choices"][0]["message"]["content"]

    async def evaluate(
        self, prompt: str, context: dict, rubric: dict
    ) -> dict:
        system = """You are an objective evaluator. Score the following
performance against the provided rubric. Return ONLY a JSON object with:
- score (float 0.0-1.0)
- reasoning (str)
- confidence (float 0.0-1.0)
- sub_scores (dict of rubric item -> float)"""

        user = f"""Context: {json.dumps(context, indent=2)}

Rubric: {json.dumps(rubric, indent=2)}

Performance to evaluate:
{prompt}

Score this performance against each rubric item."""

        result = await self.chat([
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ], temperature=0.3, max_tokens=2000)

        try:
            return json.loads(result)
        except json.JSONDecodeError:
            return {"score": 0.5, "reasoning": result, "confidence": 0.5, "sub_scores": {}}


class OllamaProvider(ModelProvider):
    """Local Ollama provider — runs models on your machine."""

    def __init__(self, base_url: str = "http://localhost:11434"):
        self.base_url = base_url
        self.model = "llama3.2"

    async def chat(self, messages: list[dict], **kwargs) -> str:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.base_url}/api/chat",
                json={
                    "model": kwargs.get("model", self.model),
                    "messages": messages,
                    "stream": False,
                },
                timeout=120,
            )
            data = resp.json()
            return data["message"]["content"]

    async def evaluate(self, prompt: str, context: dict, rubric: dict) -> dict:
        user = f"""Score this performance against the rubric.
Return JSON with: score (0.0-1.0), reasoning, confidence.

Context: {json.dumps(context)}
Rubric: {json.dumps(rubric)}
Performance: {prompt}"""

        result = await self.chat([
            {"role": "user", "content": user},
        ], temperature=0.3)
        try:
            return json.loads(result)
        except json.JSONDecodeError:
            return {"score": 0.5, "reasoning": result, "confidence": 0.3, "sub_scores": {}}


class DeterministicFallback(ModelProvider):
    """Fallback evaluator when no external provider is available."""

    async def chat(self, messages: list[dict], **kwargs) -> str:
        return "Deterministic fallback — no model provider configured."

    async def evaluate(self, prompt: str, context: dict, rubric: dict) -> dict:
        score = min(1.0, max(0.0, context.get("score", 0.5)))
        return {
            "score": score,
            "reasoning": "Deterministic evaluation (no LLM provider available)",
            "confidence": 0.7,
            "sub_scores": {k: score for k in rubric.get("items", [])},
        }


def get_provider(name: str = "auto") -> ModelProvider:
    """Get the best available model provider."""
    if name == "venice" or (name == "auto" and os.environ.get("VENICE_API_KEY")):
        return VeniceProvider()
    if name == "ollama":
        return OllamaProvider()
    return DeterministicFallback()
