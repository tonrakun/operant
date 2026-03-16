"""
agent/screenshot.py — スクリーンショット取得・差分検出・WebP変換
差分検出は「変化なし時のスキップ」のみに使用。LLMには常に全体画像を渡す。
"""
from __future__ import annotations

import asyncio
import base64
import io
import logging
from typing import Any

logger = logging.getLogger(__name__)

# 前フレームのグレースケール numpy 配列をモジュールレベルで保持
_prev_gray: Any = None

# 最後のキャプチャ情報（スケール・画像サイズ）
_last_scale: float = 1.0
_last_img_size: tuple[int, int] = (0, 0)


def get_last_capture_info() -> tuple[float, tuple[int, int]]:
    """最後のスクリーンショットの (scale, (width, height)) を返す。
    scale < 1.0 の場合、controller 側で座標を 1/scale 倍する必要がある。"""
    return _last_scale, _last_img_size


def _reset_diff_state() -> None:
    """差分検出の前フレームをリセットする"""
    global _prev_gray
    _prev_gray = None


def _capture_and_process(config: dict[str, Any]) -> bytes | None:
    """
    スクリーンショット取得 → SSIM差分検出 → リサイズ → WebP変換
    差分なし（類似度が閾値超）の場合は None を返す
    """
    global _prev_gray, _last_scale, _last_img_size

    import mss
    import numpy as np
    from PIL import Image

    scr_cfg = config.get("screenshot", {})
    max_w: int = scr_cfg.get("max_width", 1280)
    max_h: int = scr_cfg.get("max_height", 720)
    quality: int = scr_cfg.get("quality", 80)
    diff_threshold: float = scr_cfg.get("diff_threshold", 0.97)
    use_webp: bool = scr_cfg.get("format", "webp") == "webp"

    with mss.mss() as sct:
        monitor = sct.monitors[1]  # プライマリモニター
        raw = sct.grab(monitor)
        img = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")

    # リサイズ
    orig_w, orig_h = img.size
    scale = min(max_w / orig_w, max_h / orig_h, 1.0)
    if scale < 1.0:
        new_w = int(orig_w * scale)
        new_h = int(orig_h * scale)
        img = img.resize((new_w, new_h), Image.LANCZOS)
    else:
        new_w, new_h = orig_w, orig_h

    # スケール情報を保存（controller.py が座標変換に使用）
    _last_scale = scale
    _last_img_size = (new_w, new_h)

    # SSIM差分検出（変化なし時のスキップのみ。タイル分割はしない）
    gray_arr = np.array(img.convert("L"), dtype=np.float32) / 255.0

    if _prev_gray is not None and _prev_gray.shape == gray_arr.shape:
        try:
            from skimage.metrics import structural_similarity as ssim
            score = ssim(
                _prev_gray,
                gray_arr,
                data_range=1.0,
                win_size=7,
                channel_axis=None,
            )
            if score >= diff_threshold:
                # 変化なし → None を返してスキップ
                return None
        except Exception as exc:
            logger.warning("SSIM failed: %s", exc)

    _prev_gray = gray_arr

    # WebP / PNG 変換
    buf = io.BytesIO()
    fmt = "WEBP" if use_webp else "PNG"
    save_kwargs: dict[str, Any] = {}
    if use_webp:
        save_kwargs["quality"] = quality
    img.save(buf, format=fmt, **save_kwargs)
    return buf.getvalue()


async def capture(config: dict[str, Any]) -> bytes | None:
    """非同期でスクリーンショットを取得する（差分なし時はNone）"""
    return await asyncio.to_thread(_capture_and_process, config)


async def capture_force(config: dict[str, Any]) -> bytes:
    """差分検出をリセットして強制的にスクリーンショットを取得する"""
    _reset_diff_state()
    result = await asyncio.to_thread(_capture_and_process, config)
    if result is None:
        # リセット後なのでNoneは来ないはずだが念のため
        _reset_diff_state()
        result = await asyncio.to_thread(_capture_and_process, config)
    return result or b""


def encode_to_base64(data: bytes) -> str:
    return base64.b64encode(data).decode()


def make_image_message_content(data: bytes, fmt: str = "webp") -> list[dict[str, Any]]:
    """
    LLMに送るための画像コンテンツブロックを生成する
    Anthropic形式: [{"type": "image", "source": {...}}, {"type": "text", ...}]
    OpenAI形式: [{"type": "image_url", "image_url": {...}}]
    → 共通中間形式として OpenAI 形式を使い、各LLMアダプターで変換する
    """
    b64 = encode_to_base64(data)
    mime = f"image/{fmt}"
    return [
        {
            "type": "image_url",
            "image_url": {"url": f"data:{mime};base64,{b64}"},
        }
    ]
