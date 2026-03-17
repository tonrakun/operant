"""
llm/openai.py — OpenAI / Azure OpenAI 実装
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import openai

from .base import BaseLLM, build_system_prompt

logger = logging.getLogger(__name__)


class OpenAILLM(BaseLLM):
    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__(config)
        api_key = self._resolve_api_key("openai")
        self._client = openai.OpenAI(api_key=api_key)

    async def chat(
        self,
        messages: list[dict[str, Any]],
        system_prompt: str | None = None,
    ) -> str:
        sys_text = system_prompt or build_system_prompt()

        api_messages: list[dict[str, Any]] = [
            {"role": "system", "content": sys_text},
            *messages,
        ]

        def _call() -> str:
            resp = self._client.chat.completions.create(
                model=self.model,
                messages=api_messages,
            )
            if resp.usage:
                self.last_usage = {
                    "input_tokens": resp.usage.prompt_tokens,
                    "output_tokens": resp.usage.completion_tokens,
                }
            return resp.choices[0].message.content or ""

        return await asyncio.to_thread(_call)


class AzureOpenAILLM(BaseLLM):
    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__(config)
        api_key = self._resolve_api_key("openai")
        llm_cfg = config.get("llm", {})
        self._endpoint = llm_cfg.get("azure_endpoint", "")
        self._deployment = llm_cfg.get("azure_deployment", self.model)
        self._client = openai.AzureOpenAI(
            api_key=api_key,
            azure_endpoint=self._endpoint,
            api_version="2024-02-01",
        )

    async def chat(
        self,
        messages: list[dict[str, Any]],
        system_prompt: str | None = None,
    ) -> str:
        sys_text = system_prompt or build_system_prompt()

        api_messages: list[dict[str, Any]] = [
            {"role": "system", "content": sys_text},
            *messages,
        ]

        def _call() -> str:
            resp = self._client.chat.completions.create(
                model=self._deployment,
                messages=api_messages,
            )
            if resp.usage:
                self.last_usage = {
                    "input_tokens": resp.usage.prompt_tokens,
                    "output_tokens": resp.usage.completion_tokens,
                }
            return resp.choices[0].message.content or ""

        return await asyncio.to_thread(_call)
