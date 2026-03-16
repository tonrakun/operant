"""
agent/controller.py — マウス・キーボード操作
pyautogui + pygetwindow
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import pyautogui

from .screenshot import get_last_capture_info

# フェイルセーフ有効: マウスを左上に移動すると自動停止
pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.05  # 操作間の最小ウェイト（秒）

logger = logging.getLogger(__name__)


def _scale_to_screen(x: int | float, y: int | float) -> tuple[int, int]:
    """
    スクリーンショット座標 → 実際のスクリーン座標に変換する。
    LLM はリサイズ後の画像サイズ基準で座標を返すため、
    scale < 1.0 の場合は 1/scale 倍して実解像度に合わせる。
    """
    scale, _ = get_last_capture_info()
    if scale <= 0.0 or scale >= 1.0:
        return int(round(x)), int(round(y))
    return int(round(x / scale)), int(round(y / scale))


async def execute_controller_action(action: dict[str, Any]) -> str:
    """マウス・キーボード・ウィンドウ操作アクションを実行する"""
    name = action.get("action", "")

    try:
        if name == "click":
            return await _click(action)
        elif name == "double_click":
            return await _double_click(action)
        elif name == "right_click":
            return await _right_click(action)
        elif name == "drag":
            return await _drag(action)
        elif name == "scroll":
            return await _scroll(action)
        elif name == "type":
            return await _type_text(action)
        elif name == "key":
            return await _key(action)
        else:
            return f"Unknown controller action: {name}"
    except Exception as exc:
        logger.error("Controller action %s failed: %s", name, exc, exc_info=True)
        return f"Error: {exc}"


async def _click(action: dict[str, Any]) -> str:
    sx, sy = action["x"], action["y"]
    x, y = _scale_to_screen(sx, sy)
    await asyncio.to_thread(pyautogui.click, x, y)
    return f"Clicked ({x}, {y}) [screenshot: ({sx}, {sy})]"


async def _double_click(action: dict[str, Any]) -> str:
    sx, sy = action["x"], action["y"]
    x, y = _scale_to_screen(sx, sy)
    await asyncio.to_thread(pyautogui.doubleClick, x, y)
    return f"Double-clicked ({x}, {y}) [screenshot: ({sx}, {sy})]"


async def _right_click(action: dict[str, Any]) -> str:
    sx, sy = action["x"], action["y"]
    x, y = _scale_to_screen(sx, sy)
    await asyncio.to_thread(pyautogui.rightClick, x, y)
    return f"Right-clicked ({x}, {y}) [screenshot: ({sx}, {sy})]"


async def _drag(action: dict[str, Any]) -> str:
    x1, y1 = _scale_to_screen(action["x1"], action["y1"])
    x2, y2 = _scale_to_screen(action["x2"], action["y2"])
    await asyncio.to_thread(pyautogui.moveTo, x1, y1)
    await asyncio.to_thread(pyautogui.dragTo, x2, y2, duration=0.5, button="left")
    return f"Dragged ({x1},{y1}) -> ({x2},{y2})"


async def _scroll(action: dict[str, Any]) -> str:
    x, y = _scale_to_screen(action["x"], action["y"])
    direction = action.get("dir", "down")
    amount = action.get("amount", 3)
    clicks = -amount if direction == "down" else amount

    def _do() -> None:
        pyautogui.moveTo(x, y)
        pyautogui.scroll(clicks)

    await asyncio.to_thread(_do)
    return f"Scrolled {direction} x{amount} at ({x},{y})"


async def _type_text(action: dict[str, Any]) -> str:
    text = action.get("text", "")
    await asyncio.to_thread(pyautogui.write, text, interval=0.02)
    return f"Typed {len(text)} chars"


async def _key(action: dict[str, Any]) -> str:
    key = action.get("key", "")
    # "ctrl+c" のようなコンビネーションに対応
    if "+" in key:
        keys = [k.strip() for k in key.split("+")]
        await asyncio.to_thread(pyautogui.hotkey, *keys)
    else:
        await asyncio.to_thread(pyautogui.press, key)
    return f"Pressed key: {key}"
