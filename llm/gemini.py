"""
llm/gemini.py — Google Gemini 実装
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from .base import BaseLLM, build_system_prompt

logger = logging.getLogger(__name__)


class GeminiLLM(BaseLLM):
    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__(config)
        api_key = self._resolve_api_key("gemini")
        from google import genai
        self._client = genai.Client(api_key=api_key)

    async def chat(
        self,
        messages: list[dict[str, Any]],
        system_prompt: str | None = None,
    ) -> str:
        sys_text = system_prompt or build_system_prompt()

        # Gemini SDK の contents 形式に変換
        # 画像は {"type": "image_url", "image_url": {"url": "data:image/webp;base64,..."}} 形式で来る
        from google.genai import types as gtypes

        contents: list[Any] = []
        for msg in messages:
            role = "user" if msg["role"] == "user" else "model"
            content = msg["content"]

            if isinstance(content, str):
                parts = [gtypes.Part(text=content)]
            elif isinstance(content, list):
                parts = []
                for item in content:
                    if isinstance(item, dict):
                        if item.get("type") == "text":
                            parts.append(gtypes.Part(text=item["text"]))
                        elif item.get("type") == "image_url":
                            url: str = item["image_url"]["url"]
                            if url.startswith("data:"):
                                # data:image/webp;base64,<data>
                                header, b64data = url.split(",", 1)
                                mime = header.split(":")[1].split(";")[0]
                                import base64
                                raw = base64.b64decode(b64data)
                                parts.append(
                                    gtypes.Part(
                                        inline_data=gtypes.Blob(mime_type=mime, data=raw)
                                    )
                                )
            else:
                parts = [gtypes.Part(text=str(content))]

            contents.append(gtypes.Content(role=role, parts=parts))

        config_obj = gtypes.GenerateContentConfig(
            system_instruction=sys_text,
            max_output_tokens=self.max_tokens,
        )

        def _call() -> str:
            resp = self._client.models.generate_content(
                model=self.model,
                contents=contents,
                config=config_obj,
            )
            return resp.text or ""

        return await asyncio.to_thread(_call)
