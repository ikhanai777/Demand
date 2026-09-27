"""Optional LLM synthesis layer.

Turns raw clusters into named pain points with problem statements, personas, and concrete
product ideas. Two providers:

* anthropic - Claude via the official SDK (`pip install anthropic`, ANTHROPIC_API_KEY or `ant auth login`)
* openai    - any OpenAI-compatible endpoint, e.g. Nous Hermes via OpenRouter, Nous Portal,
              Ollama or LM Studio (LLM_BASE_URL, LLM_API_KEY, LLM_MODEL)

The scanner works without an LLM: heuristics already cluster, score and suggest solutions.
Inside Claude Code you usually don't need this at all - the /scan-niche command lets
Claude Code itself do the synthesis from report.json.
"""
from __future__ import annotations

import json
import os
import re
from typing import Any

from .models import PainPoint
from .text import snippet

DEFAULT_ANTHROPIC_MODEL = "claude-opus-5"
DEFAULT_OPENAI_MODEL = "nousresearch/hermes-4-405b"

SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "niche_summary": {"type": "string"},
        "pain_points": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer"},
                    "name": {"type": "string"},
                    "problem_statement": {"type": "string"},
                    "who": {"type": "string"},
                    "severity": {"type": "integer"},
                    "is_real_pain": {"type": "boolean"},
                    "existing_solutions": {"type": "array", "items": {"type": "string"}},
                    "solutions": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "type": {"type": "string"},
                                "name": {"type": "string"},
                                "one_liner": {"type": "string"},
                                "mvp_features": {"type": "array", "items": {"type": "string"}},
                                "monetization": {"type": "string"},
                                "build_effort": {"type": "string"},
                            },
                            "required": ["type", "name", "one_liner", "mvp_features", "monetization",
                                         "build_effort"],
                            "additionalProperties": False,
                        },
                    },
                },
                "required": ["id", "name", "problem_statement", "who", "severity", "is_real_pain",
                             "existing_solutions", "solutions"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["niche_summary", "pain_points"],
    "additionalProperties": False,
}

SYSTEM = """You are a product strategist who finds startup and app opportunities in raw user complaints.
You are given clusters of real posts, comments, reviews and search queries about one niche, each with a
heuristic demand score. For every cluster:
- Give it a crisp name that states the pain from the user's perspective (not a product name).
- Write a 1-2 sentence problem statement grounded only in the evidence shown.
- Identify who has the pain (persona) and rate severity 1-10.
- Set is_real_pain=false for clusters that are noise, off-topic, or just general discussion.
- List existing solutions mentioned or implied by the evidence.
- Propose 1-3 solutions buildable by a small team with an AI coding agent. Use types from:
  android_app, web_saas, ai_tool, automation, browser_extension, content, marketplace_directory,
  marketing_service. Keep MVPs to 3-6 features and name a realistic monetization model.
  build_effort is one of: weekend, 1-2 weeks, 1 month+.
Return JSON matching the schema. Keep the ids exactly as given."""


def _payload(niche: str, points: list[PainPoint]) -> str:
    blocks = []
    for p in points:
        quotes = "\n".join(f"  - ({s.source}, {s.kind}, {int(s.score)} pts) {snippet(s.body, 300)}"
                           for s in p.top_quotes(8))
        blocks.append(f"### Cluster id={p.id} score={p.score:.0f} keywords={', '.join(p.keywords)}\n"
                      f"sources={', '.join(p.sources)} signals={len(p.signals)} tags={p.tags}\n{quotes}")
    return f"Niche: {niche}\n\n" + "\n\n".join(blocks)


def _extract_json(text: str) -> dict[str, Any]:
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise ValueError("LLM returned no JSON")
    return json.loads(m.group(0))


def _anthropic(prompt: str, model: str) -> dict[str, Any]:
    import anthropic

    client = anthropic.Anthropic()
    with client.beta.messages.stream(
        model=model,
        max_tokens=64000,
        system=SYSTEM,
        thinking={"type": "adaptive"},
        output_config={"effort": "high", "format": {"type": "json_schema", "schema": SCHEMA}},
        # Server-side fallback: if the model declines, the API re-routes the request automatically.
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        msg = stream.get_final_message()
    if msg.stop_reason == "refusal":
        raise RuntimeError("model declined the request")
    text = next((b.text for b in msg.content if b.type == "text"), "")
    return json.loads(text)


def _openai_compatible(prompt: str, model: str) -> dict[str, Any]:
    import requests

    base = os.environ.get("LLM_BASE_URL", "https://openrouter.ai/api/v1").rstrip("/")
    headers = {"Content-Type": "application/json"}
    if key := os.environ.get("LLM_API_KEY") or os.environ.get("OPENROUTER_API_KEY"):
        headers["Authorization"] = f"Bearer {key}"
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM + "\n\nJSON schema:\n" + json.dumps(SCHEMA)},
            {"role": "user", "content": prompt + "\n\nRespond with a single JSON object only."},
        ],
        "temperature": 0.4,
        "response_format": {"type": "json_object"},
    }
    resp = requests.post(f"{base}/chat/completions", headers=headers, json=body, timeout=600)
    resp.raise_for_status()
    return _extract_json(resp.json()["choices"][0]["message"]["content"])


def synthesize(niche: str, points: list[PainPoint], provider: str, model: str | None = None) -> dict[str, Any]:
    """Enrich points in place; returns the raw LLM result (niche_summary etc.)."""
    if not points:
        return {}
    prompt = _payload(niche, points)
    if provider == "anthropic":
        result = _anthropic(prompt, model or os.environ.get("ANTHROPIC_MODEL", DEFAULT_ANTHROPIC_MODEL))
    elif provider in ("openai", "hermes"):
        result = _openai_compatible(prompt, model or os.environ.get("LLM_MODEL", DEFAULT_OPENAI_MODEL))
    else:
        raise ValueError(f"unknown LLM provider: {provider}")
    by_id = {p.id: p for p in points}
    for item in result.get("pain_points", []):
        p = by_id.get(item.get("id"))
        if p is None:
            continue
        p.llm = item
        # Blend the model's severity judgement into the heuristic score; drop noise hard.
        sev = max(1, min(10, int(item.get("severity", 5))))
        p.score = p.score * (0.8 + sev / 50)
        if item.get("is_real_pain") is False:
            p.score *= 0.4
    points.sort(key=lambda p: p.score, reverse=True)
    return result
