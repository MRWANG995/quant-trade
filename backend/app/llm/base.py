"""LLM 提供商抽象。当前实现：Gemini。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


class LLMError(RuntimeError):
    """LLM 调用失败。"""


@dataclass
class LLMResult:
    text: str  # 原始文本（强制 JSON 时为可解析的 JSON 串）
    parsed: Any  # text 解析后的对象（dict/list/...）
    model: str
    provider: str
    usage: dict | None = None  # 可选：token 计数


class LLMProvider(Protocol):
    name: str
    model: str

    async def generate_json(
        self,
        system: str,
        user: str,
        *,
        temperature: float = 0.4,
    ) -> LLMResult:
        ...
