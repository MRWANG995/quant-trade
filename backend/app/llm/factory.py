"""按 env 选择 LLM 提供商。"""

from __future__ import annotations

from functools import lru_cache

from app.config import get_settings
from app.llm.base import LLMError, LLMProvider
from app.llm.gemini import GeminiProvider


@lru_cache
def get_llm_provider() -> LLMProvider:
    s = get_settings()
    provider = (getattr(s, "llm_provider", "gemini") or "gemini").lower()
    if provider == "gemini":
        return GeminiProvider(
            api_key=getattr(s, "gemini_api_key", "") or "",
            model=getattr(s, "gemini_model", "gemini-2.0-flash") or "gemini-2.0-flash",
        )
    raise LLMError(f"未支持的 LLM provider: {provider}")
