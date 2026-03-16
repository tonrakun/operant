"""
llm/claude.py — Anthropic Claude 実装
Prompt Caching 対応
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import anthropic

from .base import BaseLLM, build_system_prompt

logger = logging.getLogger(__name__)


class ClaudeLLM(BaseLLM):
    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__(config)
        api_key = self._resolve_api_key("anthropic")
        self._client = anthropic.Anthropic(api_key=api_key)

    @staticmethod
    def _convert_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """OpenAI形式のメッセージをAnthropic形式に変換する"""
        import base64
        converted = []
        for msg in messages:
            content = msg["content"]
            if isinstance(content, list):
                parts: list[dict[str, Any]] = []
                for item in content:
                    if isinstance(item, dict):
                        if item.get("type") == "text":
                            parts.append({"type": "text", "text": item["text"]})
                        elif item.get("type") == "image_url":
                            url: str = item["image_url"]["url"]
                            if url.startswith("data:"):
                                header, b64data = url.split(",", 1)
                                media_type = header.split(":")[1].split(";")[0]
                                parts.append({
                                    "type": "image",
                                    "source": {
                                        "type": "base64",
                                        "media_type": media_type,
                                        "data": b64data,
                                    },
                                })
                converted.append({"role": msg["role"], "content": parts})
            else:
                converted.append({"role": msg["role"], "content": content})
        return converted

    async def chat(
        self,
        messages: list[dict[str, Any]],
        system_prompt: str | None = None,
    ) -> str:
        sys_text = system_prompt or build_system_prompt()

        # システムプロンプトをキャッシュブロックで包む
        system_blocks: list[dict[str, Any]] = [
            {
                "type": "text",
                "text": sys_text,
                "cache_control": {"type": "ephemeral"},
            }
        ]

        # OpenAI → Anthropic 形式変換
        api_messages = self._convert_messages(messages)

        # Anthropic API はメッセージの末尾が user である必要がある
        # コンテキスト管理のバグで assistant が末尾になった場合の安全弁
        while api_messages and api_messages[-1]["role"] == "assistant":
            api_messages.pop()
        if not api_messages:
            api_messages = [{"role": "user", "content": "[start]"}]

        def _call() -> str:
            resp = self._client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                system=system_blocks,
                messages=api_messages,
            )
            raw = resp.content[0].text if resp.content else ""
            if not raw.startswith("THINK:") and not raw.startswith("DONE:") and not raw.startswith("ACT:"):
                raw = "THINK: " + raw
            return raw

        return await asyncio.to_thread(_call)
