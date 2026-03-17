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
# モデル料金テーブル (USD / 1M tokens: input, output)
# ---------------------------------------------------------------------------
_MODEL_PRICING: dict[str, tuple[float, float]] = {
    "claude-opus":          (15.0,  75.0),
    "claude-sonnet":        (3.0,   15.0),
    "claude-haiku":         (0.8,   4.0),
    "gpt-4o-mini":          (0.15,  0.60),
    "gpt-4o":               (2.5,   10.0),
    "o1":                   (15.0,  60.0),
    "gemini-1.5-pro":       (1.25,  5.0),
    "gemini-1.5-flash":     (0.075, 0.30),
    "gemini-2.0-flash":     (0.10,  0.40),
}


def _get_model_pricing(model: str) -> tuple[float, float]:
    m = model.lower()
    for key, pricing in _MODEL_PRICING.items():
        if key in m:
            return pricing
    return (3.0, 15.0)


def _calc_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    inp, out = _get_model_pricing(model)
    return (input_tokens * inp + output_tokens * out) / 1_000_000


# ---------------------------------------------------------------------------
# レスポンスパーサー
# ---------------------------------------------------------------------------

def _extract_act_json(text: str) -> dict[str, Any] | None:
    """
    テキスト全体から ACT: 以降の最初の JSON オブジェクトをブレースバランスで抽出する。
    """
    act_match = re.search(r"ACT\s*:", text, re.IGNORECASE)
    if not act_match:
        return None

    remainder = text[act_match.end():]
    remainder = re.sub(r"^[\s\n]*```(?:json)?[\s\n]*", "", remainder)

    start = remainder.find("{")
    if start < 0:
        return None

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


def parse_response(text: str) -> tuple[str | None, str | None, dict[str, Any] | None, str | None]:
    """
    LLMレスポンスをパースして (think, reply, act, done) を返す。
    - think: THINK: タグの内容（エージェント内部推論、薄く表示）
    - reply: REPLY: タグの内容（ユーザー向けテキスト応答、強調表示）
    - act:   ACT: タグのJSON（ツール呼び出し）
    - done:  DONE: タグの内容（タスク完了）
    """
    think: str | None = None
    reply: str | None = None
    done: str | None = None

    # 複数行THINK:/REPLY:/DONE: に対応するため行ベースでパース
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        stripped = lines[i].strip()
        if stripped.upper().startswith("THINK:") and think is None:
            think = stripped[6:].strip()
        elif stripped.upper().startswith("REPLY:") and reply is None:
            reply = stripped[6:].strip()
            # REPLY: の後に続く行もテキストとして連結（次のタグが来るまで）
            j = i + 1
            extra_lines = []
            while j < len(lines):
                next_stripped = lines[j].strip()
                if re.match(r'^(THINK|ACT|DONE|REPLY)\s*:', next_stripped, re.IGNORECASE):
                    break
                extra_lines.append(lines[j])
                j += 1
            if extra_lines:
                reply = reply + "\n" + "\n".join(extra_lines).strip()
                reply = reply.strip()
            i = j
            continue
        elif stripped.upper().startswith("DONE:") and done is None:
            done = stripped[5:].strip()
        i += 1

    act = _extract_act_json(text)

    return think, reply, act, done


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
        # セッション累計トークン・コスト
        self._session_input_tokens: int = 0
        self._session_output_tokens: int = 0
        self._session_cost_usd: float = 0.0

    def is_running(self) -> bool:
        return self._task is not None and not self._task.done()

    def emergency_stop(self) -> None:
        self._stop_event.set()

    async def start_task(
        self,
        user_input: str,
        send: SendFunc,
    ) -> None:
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

        # ループ検出用: 直近アクション署名と連続カウント
        _last_act_sig: str | None = None
        _consecutive_act_count: int = 0
        _MAX_CONSECUTIVE = 3

        await send({"type": "status", "running": True})

        screenshot_data: bytes | None = await capture_force(self.config)
        if screenshot_data:
            b64 = encode_to_base64(screenshot_data)
            await send({"type": "screenshot", "data": b64})
        screenshot_content = (
            make_image_message_content(screenshot_data, fmt)
            if screenshot_data
            else None
        )

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
                if self._stop_event.is_set():
                    await send({"type": "log", "content": "Emergency stop requested"})
                    break

                elapsed = time.monotonic() - start_time
                if elapsed > loop_timeout:
                    await send({"type": "error", "content": f"Task timeout ({loop_timeout}s)"})
                    break

                messages = self.context.build_messages(
                    user_input=current_user_msg,
                    screenshot_content=screenshot_content,
                )
                screenshot_content = None

                try:
                    response = await self.llm.chat(messages)
                except Exception as exc:
                    logger.error("LLM call failed: %s", exc, exc_info=True)
                    await send({"type": "error", "content": f"LLM error: {exc}"})
                    break

                # トークン使用量・コスト計算
                usage = self.llm.last_usage
                inp = usage.get("input_tokens", 0)
                out = usage.get("output_tokens", 0)
                turn_cost = _calc_cost(self.llm.model, inp, out)
                self._session_input_tokens += inp
                self._session_output_tokens += out
                self._session_cost_usd += turn_cost
                await send({
                    "type": "cost",
                    "input_tokens": inp,
                    "output_tokens": out,
                    "turn_cost_usd": turn_cost,
                    "session_input_tokens": self._session_input_tokens,
                    "session_output_tokens": self._session_output_tokens,
                    "session_cost_usd": self._session_cost_usd,
                })

                self.context.add_user(current_user_msg)
                self.context.add_assistant(response)

                think, reply, act, done = parse_response(response)

                if think is None and reply is None and act is None and done is None:
                    logger.warning("Failed to parse LLM response: %s", response[:200])
                    await send({"type": "log", "content": f"Parse warning: {response[:200]}"})
                    break

                # THINK 送信（内部推論、薄く表示）
                if think:
                    await send({"type": "think", "content": think})

                # REPLY 送信（ユーザー向け応答、強調表示）
                if reply:
                    await send({"type": "reply", "content": reply})

                # DONE で終了
                if done:
                    await send({"type": "done", "content": done})
                    break

                # ACT 実行
                if act:
                    action_name = act.get("action", "")

                    # ループ検出
                    act_sig = json.dumps(act, sort_keys=True, ensure_ascii=False)
                    if act_sig == _last_act_sig:
                        _consecutive_act_count += 1
                    else:
                        _consecutive_act_count = 1
                        _last_act_sig = act_sig

                    if _consecutive_act_count >= _MAX_CONSECUTIVE:
                        await send({
                            "type": "error",
                            "content": f"Loop detected: same action repeated {_MAX_CONSECUTIVE} times consecutively. Stopping.",
                        })
                        break

                    await send({"type": "log", "content": f"ACT: {json.dumps(act, ensure_ascii=False)}"})

                    if action_name == "screenshot":
                        data = await capture_force(self.config)
                        if data:
                            b64 = encode_to_base64(data)
                            await send({"type": "screenshot", "data": b64})
                            screenshot_content = make_image_message_content(data, fmt)
                            _, img_size = get_last_capture_info()
                            size_note = f" [Size: {img_size[0]}x{img_size[1]}px]" if img_size[0] > 0 else ""
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
                        await asyncio.sleep(
                            self.config.get("screenshot", {}).get("capture_delay_ms", 500) / 1000
                        )
                        data = await capture(self.config)
                        if data:
                            b64 = encode_to_base64(data)
                            await send({"type": "screenshot", "data": b64})
                            screenshot_content = make_image_message_content(data, fmt)
                            _, img_size = get_last_capture_info()
                            size_note = f" [Size: {img_size[0]}x{img_size[1]}px]" if img_size[0] > 0 else ""
                            current_user_msg = f"[Action result: {result}]{size_note}"
                        else:
                            current_user_msg = f"[Action result: {result}]"

                    else:
                        result = await execute_action(act, self.config)
                        await send({"type": "log", "content": f"Result: {result[:500]}"})
                        current_user_msg = f"[Tool result]\n{result}"

                else:
                    # ACTなし（REPLY/THINKのみ）= 会話ターン → ループ終了
                    break

        except Exception as exc:
            logger.error("Agent loop error: %s", exc, exc_info=True)
            await send({"type": "error", "content": f"Agent error: {exc}"})
        finally:
            await send({"type": "status", "running": False})
