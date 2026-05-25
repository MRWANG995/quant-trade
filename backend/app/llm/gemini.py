"""Google Gemini 提供商（免费层 Gemini 2.0 Flash）。"""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from app.llm.base import LLMError, LLMResult

logger = logging.getLogger(__name__)

GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta"


class GeminiProvider:
    name = "gemini"

    def __init__(self, api_key: str, model: str = "gemini-2.0-flash", timeout: float = 30.0) -> None:
        if not api_key:
            raise LLMError("GEMINI_API_KEY 未配置")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    async def generate_json(
        self,
        system: str,
        user: str,
        *,
        temperature: float = 0.4,
    ) -> LLMResult:
        url = f"{GEMINI_API_BASE}/models/{self.model}:generateContent"
        # Gemini 用 systemInstruction 承载 system prompt，可比拼到 user
        payload: dict[str, Any] = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": {
                "temperature": temperature,
                "responseMimeType": "application/json",
                "maxOutputTokens": 4096,
            },
        }
        params = {"key": self.api_key}
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(url, params=params, json=payload)
        except httpx.HTTPError as exc:
            raise LLMError(f"网络错误：{exc}") from exc

        if resp.status_code == 401 or resp.status_code == 403:
            raise LLMError("Gemini 鉴权失败，请检查 GEMINI_API_KEY")
        if resp.status_code == 429:
            raise LLMError("Gemini 触发限流，请稍后再试（免费层 15 RPM / 1500 RPD）")
        if resp.status_code >= 400:
            raise LLMError(f"Gemini HTTP {resp.status_code}：{resp.text[:300]}")

        data = resp.json()
        candidates = data.get("candidates") or []
        if not candidates:
            block_reason = (data.get("promptFeedback") or {}).get("blockReason")
            raise LLMError(f"Gemini 未返回内容（blockReason={block_reason}）")
        parts = (candidates[0].get("content") or {}).get("parts") or []
        text = "".join(p.get("text", "") for p in parts).strip()
        if not text:
            raise LLMError("Gemini 返回了空文本")

        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as exc:
            # 兜底：找第一个 { 到最后一个 } 之间的子串再解一次
            start = text.find("{")
            end = text.rfind("}")
            if start >= 0 and end > start:
                try:
                    parsed = json.loads(text[start : end + 1])
                except json.JSONDecodeError:
                    raise LLMError(f"Gemini 返回非合法 JSON：{text[:200]}") from exc
            else:
                raise LLMError(f"Gemini 返回非合法 JSON：{text[:200]}") from exc

        usage = data.get("usageMetadata")
        return LLMResult(text=text, parsed=parsed, model=self.model, provider=self.name, usage=usage)
