"""Thin client for NVIDIA Nemotron models served on Nebius Token Factory.

Token Factory exposes an OpenAI-compatible API, so the official `openai` SDK is
used with Nebius's base URL. Each pipeline step is routed to the smallest
Nemotron model that does it well:

  NANO   -> fast structured extraction
  VISION -> reading screenshots (Nemotron 3.5 Super VL) / scanned agreements
  SUPER  -> summarising web evidence about the lender
  ULTRA  -> the final reasoning/verdict and Telugu/Hindi (smaller models garbled Telugu)

Model IDs are configurable because the Token Factory catalog evolves; set them
in Streamlit secrets or environment variables.
"""
from __future__ import annotations

import base64
import json
import os
import re
import time
from dataclasses import dataclass, field

DEFAULT_BASE_URL = "https://api.tokenfactory.nebius.com/v1/"

DEFAULT_MODELS = {
    "NANO": "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B",
    "SUPER": "nvidia/nemotron-3-super-120b-a12b",
    "ULTRA": "nvidia/Nemotron-3-Ultra-550b-a55b",
    "VISION": "nvidia/Nemotron-3.5-Super-VL",
}


def _setting(name: str, default: str | None = None) -> str | None:
    """Read from Streamlit secrets if available, else the environment."""
    try:
        import streamlit as st  # noqa: WPS433
        if name in st.secrets:
            return str(st.secrets[name])
    except Exception:
        pass
    return os.environ.get(name, default)


@dataclass
class CallLog:
    step: str
    model: str
    seconds: float
    tokens: int | None = None


@dataclass
class NemotronClient:
    api_key: str
    base_url: str = DEFAULT_BASE_URL
    models: dict = field(default_factory=lambda: dict(DEFAULT_MODELS))
    log: list[CallLog] = field(default_factory=list)

    @classmethod
    def from_settings(cls) -> "NemotronClient | None":
        key = _setting("NEBIUS_API_KEY")
        if not key:
            return None
        models = {tier: _setting(f"MODEL_{tier}", default) for tier, default in DEFAULT_MODELS.items()}
        return cls(api_key=key, base_url=_setting("NEBIUS_BASE_URL", DEFAULT_BASE_URL), models=models)

    def _client(self):
        from openai import OpenAI
        return OpenAI(api_key=self.api_key, base_url=self.base_url, timeout=120)

    def chat(self, tier: str, step: str, messages: list[dict], max_tokens: int = 3000, temperature: float = 0.2) -> str:
        """One completion. Nemotron reasoning tokens count against max_tokens, so if the model stops
        for length with no answer, retry once with double the budget."""
        model = self.models[tier]
        t0 = time.time()
        budget = max_tokens
        text, usage = "", None
        for _ in range(2):
            resp = self._client().chat.completions.create(
                model=model, messages=messages, max_tokens=budget, temperature=temperature)
            choice = resp.choices[0]
            text = strip_reasoning(choice.message.content or "")
            usage = getattr(resp, "usage", None)
            if text or choice.finish_reason != "length":
                break
            budget *= 2
        self.log.append(CallLog(step, model, round(time.time() - t0, 2), getattr(usage, "total_tokens", None)))
        return text

    def chat_json(self, tier: str, step: str, system: str, user, max_tokens: int = 3000) -> dict:
        """Ask for JSON, validate it parses, retry once with the parse error."""
        content = user if isinstance(user, list) else str(user)
        messages = [{"role": "system", "content": system}, {"role": "user", "content": content}]
        last_err = None
        for _ in range(2):
            raw = self.chat(tier, step, messages, max_tokens=max_tokens, temperature=0.1)
            try:
                return extract_json(raw)
            except ValueError as e:
                last_err = e
                messages += [{"role": "assistant", "content": raw},
                             {"role": "user", "content": f"That was not valid JSON ({e}). Reply with only the JSON object."}]
        raise ValueError(f"{step}: model did not return valid JSON: {last_err}")

    @staticmethod
    def image_part(image_bytes: bytes, mime: str = "image/png") -> dict:
        b64 = base64.b64encode(image_bytes).decode()
        return {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}}


def strip_reasoning(text: str) -> str:
    """Nemotron reasoning modes may emit <think>...</think>; drop it."""
    return re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()


def extract_json(text: str) -> dict:
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.S)
    if fence:
        text = fence.group(1)
    else:
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end == -1:
            raise ValueError("no JSON object found")
        text = text[start:end + 1]
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(str(e)) from e
