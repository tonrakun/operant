"""
llm/ollama.py — Ollama ローカル LLM 実装
Ollama の OpenAI 互換 API (/v1/chat/completions) を使用
Vision 対応モデル（llava 等）でスクリーンショット操作が可能
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from .base import BaseLLM, build_system_prompt

logger = logging.getLogger(__name__)


class OllamaLLM(BaseLLM):
    """Ollama ローカル LLM プロバイダー（OpenAI 互換 API 使用）"""

    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__(config)
        llm_cfg = config.get("llm", {})
        self._base_url = llm_cfg.get("ollama_base_url", "http://localhost:11434")
        if not self.model:
            self.model = "llava"

    async def chat(
        self,
        messages: list[dict[str, Any]],
        system_prompt: str | None = None,
    ) -> str:
        sys_text = system_prompt or build_system_prompt()

        import openai
        client = openai.OpenAI(
            api_key="ollama",  # Ollama は API キー不要（任意の値を設定）
            base_url=f"{self._base_url}/v1",
        )

        api_messages: list[dict[str, Any]] = [
            {"role": "system", "content": sys_text},
            *messages,
        ]

        def _call() -> str:
            resp = client.chat.completions.create(
                model=self.model,
                max_tokens=self.max_tokens,
                messages=api_messages,
            )
            raw = resp.choices[0].message.content or ""
            if not raw.startswith("THINK:") and not raw.startswith("DONE:") and not raw.startswith("ACT:"):
                raw = "THINK: " + raw
            return raw

        return await asyncio.to_thread(_call)
