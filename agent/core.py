"""
agent/core.py — エージェントメインループ
LLM呼び出し → レスポンスパース → アクション実行 → ループ
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from typing import Any, Callable, Awaitable

from .context import ConversationContext
from .controller import execute_controller_action
from .screenshot import (
    capture,
    capture_force,
    encode_to_base64,
    get_last_capture_info,
    make_image_message_content,
)
from .tools import execute_action
from llm.base import load_llm

logger = logging.getLogger(__name__)

# WebSocket 送信コールバックの型
SendFunc = Callable[[dict[str, Any]], Awaitable[None]]

# コントローラーアクション名一覧
_CONTROLLER_ACTIONS = {"click", "double_click", "right_click", "drag", "scroll", "type", "key"}


# ---------------------------------------------------------------------------
# レスポンスパーサー
# ---------------------------------------------------------------------------

def _extract_act_json(text: str) -> dict[str, Any] | None:
    """
    テキスト全体から ACT: 以降の最初の JSON オブジェクトをブレースバランスで抽出する。
    対応パターン:
      - ACT: {"action": ...}           （同一行・単行JSON）
      - ACT:\n{"action": ...}          （次行にJSON）
      - ACT:\n```json\n{"action": ...} （マークダウンコードブロック）
      - ACT: {\n  "action": ...\n}     （複数行JSON）
    """
    # ACT: の位置を検索（大文字小文字を許容）
    act_match = re.search(r"ACT\s*:", text, re.IGNORECASE)
    if not act_match:
        return None

    remainder = text[act_match.end():]

    # マークダウンコードブロック (```json ... ``` または ``` ... ```) を除去
    remainder = re.sub(r"^[\s\n]*```(?:json)?[\s\n]*", "", remainder)

    # 最初の { を探す
    start = remainder.find("{")
    if start < 0:
        return None

    # ブレースバランスで JSON オブジェクトの終端を特定
    depth = 0
    in_string = False
    escape_next = False
    for i in range(start, len(remainder)):
        c = remainder[i]
        if escape_next:
            escape_next = False
            continue
        if c == "\\" and in_string:
            escape_next = True
            continue
        if c == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                json_str = remainder[start:i + 1]
                try:
                    return json.loads(json_str)
                except json.JSONDecodeError:
                    logger.warning("Failed to parse ACT JSON: %s", json_str[:300])
                    return None

    logger.warning("ACT JSON brace not closed in response: %s", remainder[:200])
    return None


def parse_response(text: str) -> tuple[str | None, dict[str, Any] | None, str | None]:
    """
    LLMレスポンスをパースして (think, act, done) を返す。
    パース失敗時は (None, None, None)。
    ACT JSON は複数行・コードブロックに対応したブレースバランス方式で抽出する。
    """
    think: str | None = None
    done: str | None = None

    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("THINK:") and think is None:
            think = stripped[len("THINK:"):].strip()
        elif stripped.startswith("DONE:") and done is None:
            done = stripped[len("DONE:"):].strip()

    # ACT は全文から抽出（複数行・コードブロック対応）
    act = _extract_act_json(text)

    return think, act, done


# ---------------------------------------------------------------------------
# エージェントコア
# ---------------------------------------------------------------------------

class AgentCore:
    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config
        self.llm = load_llm(config)
        self.context = ConversationContext(
            max_turns=config.get("web", {}).get("context_history", 10)
        )
        self._stop_event = asyncio.Event()
        self._task: asyncio.Task | None = None

    def is_running(self) -> bool:
        return self._task is not None and not self._task.done()

    def emergency_stop(self) -> None:
        self._stop_event.set()

    async def start_task(
        self,
        user_input: str,
        send: SendFunc,
    ) -> None:
        """タスクをバックグラウンドで開始する"""
        if self.is_running():
            await send({"type": "error", "content": "Agent is already running"})
            return

        self._stop_event.clear()
        self._task = asyncio.create_task(
            self._run_loop(user_input, send),
            name="agent_loop",
        )

    async def _run_loop(self, user_input: str, send: SendFunc) -> None:
        """エージェントメインループ"""
        loop_timeout = self.config.get("agent", {}).get("loop_timeout", 300)
        start_time = time.monotonic()
        fmt = self.config.get("screenshot", {}).get("format", "webp")

        await send({"type": "status", "running": True})

        # 最初のスクリーンショットを強制取得
        screenshot_data: bytes | None = await capture_force(self.config)
        if screenshot_data:
            b64 = encode_to_base64(screenshot_data)
            await send({"type": "screenshot", "data": b64})
        screenshot_content = (
            make_image_message_content(screenshot_data, fmt)
            if screenshot_data
            else None
        )

        # 今回のターンに渡すユーザーメッセージ（最初はユーザー入力）
        current_user_msg = user_input
        if screenshot_data:
            _, img_size = get_last_capture_info()
            if img_size[0] > 0:
                current_user_msg += (
                    f"\n[Screenshot size: {img_size[0]}x{img_size[1]}px — "
                    f"use these pixel coordinates in mouse actions]"
                )

        try:
            while True:
                # 緊急停止チェック
                if self._stop_event.is_set():
                    await send({"type": "log", "content": "Emergency stop requested"})
                    break

                # タイムアウトチェック
                elapsed = time.monotonic() - start_time
                if elapsed > loop_timeout:
                    await send({"type": "error", "content": f"Task timeout ({loop_timeout}s)"})
                    break

                # LLM呼び出し用メッセージ構築
                # current_user_msg + screenshot_content を末尾に付けて送る
                messages = self.context.build_messages(
                    user_input=current_user_msg,
                    screenshot_content=screenshot_content,
                )
                screenshot_content = None  # スクショは1ターンに1回のみ

                try:
                    response = await self.llm.chat(messages)
                except Exception as exc:
                    logger.error("LLM call failed: %s", exc, exc_info=True)
                    await send({"type": "error", "content": f"LLM error: {exc}"})
                    break

                # コンテキストに今回のターンを追加（テキストのみ）
                self.context.add_user(current_user_msg)
                self.context.add_assistant(response)

                # レスポンスパース
                think, act, done = parse_response(response)

                if think is None and act is None and done is None:
                    logger.warning("Failed to parse LLM response: %s", response[:200])
                    await send({"type": "log", "content": f"Parse warning: {response[:200]}"})
                    break

                # THINK 送信
                if think:
                    await send({"type": "think", "content": think})

                # DONE で終了
                if done:
                    await send({"type": "done", "content": done})
                    break

                # ACT 実行
                if act:
                    action_name = act.get("action", "")
                    await send({"type": "log", "content": f"ACT: {json.dumps(act, ensure_ascii=False)}"})

                    if action_name == "screenshot":
                        # スクリーンショットをリクエスト
                        data = await capture_force(self.config)
                        if data:
                            b64 = encode_to_base64(data)
                            await send({"type": "screenshot", "data": b64})
                            screenshot_content = make_image_message_content(data, fmt)
                            _, img_size = get_last_capture_info()
                            size_note = (
                                f" [Size: {img_size[0]}x{img_size[1]}px]"
                                if img_size[0] > 0 else ""
                            )
                            current_user_msg = f"[Screenshot taken{size_note}]"
                        else:
                            current_user_msg = "[Screenshot: no change detected]"

                    elif action_name == "done":
                        summary = act.get("summary", "")
                        await send({"type": "done", "content": summary})
                        break

                    elif action_name in _CONTROLLER_ACTIONS:
                        result = await execute_controller_action(act)
                        await send({"type": "log", "content": f"Result: {result}"})
                        # コントローラー操作後は差分スクショを自動取得
                        await asyncio.sleep(
                            self.config.get("screenshot", {}).get("capture_delay_ms", 500) / 1000
                        )
                        data = await capture(self.config)
                        if data:
                            b64 = encode_to_base64(data)
                            await send({"type": "screenshot", "data": b64})
                            screenshot_content = make_image_message_content(data, fmt)
                            _, img_size = get_last_capture_info()
                            size_note = (
                                f" [Size: {img_size[0]}x{img_size[1]}px]"
                                if img_size[0] > 0 else ""
                            )
                            current_user_msg = f"[Action result: {result}]{size_note}"
                        else:
                            current_user_msg = f"[Action result: {result}]"

                    else:
                        # テキスト/ファイル/ツール系アクション
                        result = await execute_action(act, self.config)
                        await send({"type": "log", "content": f"Result: {result[:500]}"})
                        current_user_msg = f"[Tool result]\n{result}"

                else:
                    # ACTなし（THINKのみ）= 質問・確認待ち → ループ終了
                    break

        except Exception as exc:
            logger.error("Agent loop error: %s", exc, exc_info=True)
            await send({"type": "error", "content": f"Agent error: {exc}"})
        finally:
            await send({"type": "status", "running": False})
