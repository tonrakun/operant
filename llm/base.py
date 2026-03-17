"""
llm/base.py — LLM抽象基底クラス・システムプロンプト・ファクトリ
"""
from __future__ import annotations

import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# システムプロンプト構成
# ---------------------------------------------------------------------------

_FIXED_SYSTEM_PROMPT = """\
You are Operant, an autonomous Windows desktop agent.
You control the user's PC by analyzing screenshots and using the available tools.

## Output Format
Always respond using EXACTLY one of these patterns:

Pattern 1 — Think only (conversation, clarification, no action):
THINK: <1-2 sentences describing situation/intent>

Pattern 2 — Think and act (execute an operation):
THINK: <1-2 sentences describing situation/intent>
ACT: {"action": "<action_name>", ...parameters}

Pattern 3 — Task complete:
DONE: <one-line summary of what was accomplished>

## Available Actions
### Mouse / Keyboard
{"action": "click",        "x": 320, "y": 450}
{"action": "double_click", "x": 320, "y": 450}
{"action": "right_click",  "x": 320, "y": 450}
{"action": "drag",         "x1": 100, "y1": 100, "x2": 400, "y2": 400}
{"action": "scroll",       "x": 500, "y": 300, "dir": "down", "amount": 3}
{"action": "type",         "text": "hello world"}
{"action": "key",          "key": "enter"}

### Text / File Tools (prefer these over screenshots when possible)
{"action": "cmd",            "command": "dir C:\\Users", "timeout": 30}
{"action": "file_read",      "path": "C:/foo.txt"}
{"action": "file_write",     "path": "C:/foo.txt", "content": "...", "mode": "overwrite"}
{"action": "dir_list",       "path": "C:/project"}
{"action": "clipboard_read"}
{"action": "clipboard_write","text": "..."}
{"action": "get_windows"}
{"action": "get_processes"}
{"action": "get_ui_text",    "window": "Notepad"}
{"action": "get_env",        "key": "PATH"}
{"action": "get_sysinfo"}

### Screenshot (only request when visual confirmation is needed)
{"action": "screenshot"}

### Web (only if enabled in config)
{"action": "web_fetch", "url": "https://example.com/docs"}

### Control
{"action": "wait",   "reason": "waiting for load", "ms": 1000}
{"action": "done",   "summary": "task complete summary"}

## Coordinate System
- Screenshots are resized before being sent to you (e.g., 1920×1080 screen may appear as 1280×720)
- The message text will tell you the screenshot size: `[Screenshot size: WxHpx]`
- Always use coordinates based on the screenshot pixel dimensions shown in the image
- The system automatically scales your coordinates to the real screen — do NOT manually adjust
- Example: if screenshot is 1280×720 and you want to click the center, use x=640, y=360

## Rules
- Start every response with either THINK:, or DONE:
- Only one ACT: per response (the first one is executed; additional ones are ignored)
- Never include markdown code fences around ACT JSON
- Keep THINK: to 1-2 sentences maximum
- Tool selection priority: text tools → get_ui_text → screenshot (last resort)
"""


def _load_operant_md() -> str:
    path = Path(__file__).parent.parent / "OPERANT.md"
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""


def build_system_prompt() -> str:
    """固定部 + OPERANT.md を結合してシステムプロンプトを返す"""
    operant = _load_operant_md()
    if operant:
        return _FIXED_SYSTEM_PROMPT + "\n\n---\n\n" + operant
    return _FIXED_SYSTEM_PROMPT


# ---------------------------------------------------------------------------
# 抽象基底クラス
# ---------------------------------------------------------------------------

class BaseLLM(ABC):
    """全LLMプロバイダー共通インターフェース"""

    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config
        self.llm_config: dict[str, Any] = config.get("llm", {})
        self.max_tokens: int = self.llm_config.get("max_tokens", 256)
        self.model: str = self.llm_config.get("model", "")

    def _resolve_api_key(self, key_name: str) -> str:
        """config の api_keys から環境変数参照 (${VAR}) を解決して返す"""
        raw = self.config.get("api_keys", {}).get(key_name, "")
        if raw.startswith("${") and raw.endswith("}"):
            env_var = raw[2:-1]
            val = os.environ.get(env_var, "")
            if not val:
                raise ValueError(f"Environment variable {env_var} is not set")
            return val
        return raw

    @abstractmethod
    async def chat(
        self,
        messages: list[dict[str, Any]],
        system_prompt: str | None = None,
    ) -> str:
        """
        LLMにメッセージを送り、テキストレスポンスを返す。
        messages: [{"role": "user"|"assistant", "content": str | list}]
        system_prompt: None の場合は build_system_prompt() を使用
        """
        ...


# ---------------------------------------------------------------------------
# ファクトリ
# ---------------------------------------------------------------------------

def load_llm(config: dict[str, Any]) -> BaseLLM:
    """設定からLLMインスタンスを生成する"""
    provider = config.get("llm", {}).get("provider", "claude")

    if provider == "claude":
        from .claude import ClaudeLLM
        return ClaudeLLM(config)
    elif provider == "openai":
        from .openai import OpenAILLM
        return OpenAILLM(config)
    elif provider == "azure_openai":
        from .openai import AzureOpenAILLM
        return AzureOpenAILLM(config)
    elif provider == "gemini":
        from .gemini import GeminiLLM
        return GeminiLLM(config)
    elif provider == "ollama":
        from .ollama import OllamaLLM
        return OllamaLLM(config)
    else:
        raise ValueError(f"Unsupported LLM provider: {provider}")
