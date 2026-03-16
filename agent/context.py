"""
agent/context.py — 会話コンテキスト管理
会話履歴の保持・刈り込み・古いターンの要約圧縮
スクリーンショットは履歴に含めない（毎回最新1枚のみ渡す設計）
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class ConversationContext:
    """
    会話履歴を管理する。
    - テキストのみ保持（スクリーンショットは除外）
    - 直近 N ターンを保持し、古いターンは1行サマリーに圧縮
    """

    def __init__(self, max_turns: int = 10) -> None:
        self._max_turns = max_turns
        # {"role": "user"|"assistant", "content": str}
        self._history: list[dict[str, Any]] = []

    def add_user(self, text: str) -> None:
        self._history.append({"role": "user", "content": text})
        self._trim()

    def add_assistant(self, text: str) -> None:
        self._history.append({"role": "assistant", "content": text})
        self._trim()

    def _trim(self) -> None:
        """直近 max_turns ターンを超えた古いターンを圧縮する"""
        # 1ターン = user + assistant ペア（必ず2件単位で削除）
        max_msgs = self._max_turns * 2
        if len(self._history) <= max_msgs:
            return

        # 超過分をペア単位（偶数）に切り上げて先頭から削除
        excess = len(self._history) - max_msgs
        excess = excess + (excess % 2)  # 偶数に切り上げ（ペア単位）
        excess = min(excess, len(self._history))

        old_msgs = self._history[:excess]
        self._history = self._history[excess:]

        # 古いターンを1行サマリーとしてシステムノートに変換
        summary_parts: list[str] = []
        for msg in old_msgs:
            role = "User" if msg["role"] == "user" else "Agent"
            content = str(msg["content"])
            snippet = content[:80].replace("\n", " ")
            summary_parts.append(f"[{role}]: {snippet}...")

        summary = "Earlier conversation (summarized):\n" + "\n".join(summary_parts)

        # サマリーを先頭 user メッセージの冒頭に追記（必ず user で始まる）
        if self._history and self._history[0]["role"] == "user":
            existing = self._history[0]["content"]
            self._history[0]["content"] = summary + "\n\n" + existing
        else:
            self._history.insert(0, {"role": "user", "content": summary})

    def build_messages(
        self,
        user_input: str,
        screenshot_content: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        """
        LLMに渡すメッセージリストを構築する。
        スクリーンショットは最新1枚のみ user メッセージの末尾に付加する。
        """
        messages: list[dict[str, Any]] = list(self._history)

        # 今回の user ターンを構築
        if screenshot_content:
            # テキスト + 画像のマルチパートコンテンツ
            content: Any = [
                {"type": "text", "text": user_input},
                *screenshot_content,
            ]
        else:
            content = user_input

        messages.append({"role": "user", "content": content})
        return messages

    def clear(self) -> None:
        self._history.clear()

    @property
    def turn_count(self) -> int:
        return len(self._history) // 2
