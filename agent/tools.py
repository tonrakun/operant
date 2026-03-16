"""
agent/tools.py — テキスト直接処理ツール群
全アクションを execute_action(action: dict) -> str で統一処理
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import subprocess
from pathlib import Path
from typing import Any

import aiofiles
import psutil
import pyperclip

logger = logging.getLogger(__name__)


async def execute_action(action: dict[str, Any], config: dict[str, Any]) -> str:
    """
    アクションを実行して結果を文字列で返す。
    screenshot / controller 系アクションはここでは扱わない（core.py で処理）。
    """
    name = action.get("action", "")

    try:
        if name == "cmd":
            return await _cmd(action, config)
        elif name == "file_read":
            return await _file_read(action)
        elif name == "file_write":
            return await _file_write(action)
        elif name == "dir_list":
            return await _dir_list(action)
        elif name == "clipboard_read":
            return await _clipboard_read()
        elif name == "clipboard_write":
            return await _clipboard_write(action)
        elif name == "get_processes":
            return await _get_processes()
        elif name == "get_windows":
            return await _get_windows()
        elif name == "get_ui_text":
            return await _get_ui_text(action)
        elif name == "get_env":
            return await _get_env(action)
        elif name == "get_sysinfo":
            return await _get_sysinfo()
        elif name == "web_fetch":
            return await _web_fetch(action, config)
        elif name == "wait":
            return await _wait(action)
        else:
            return f"Unknown action: {name}"
    except Exception as exc:
        logger.error("Action %s failed: %s", name, exc, exc_info=True)
        return f"Error executing {name}: {exc}"


# ---------------------------------------------------------------------------
# 各ツール実装
# ---------------------------------------------------------------------------

async def _cmd(action: dict[str, Any], config: dict[str, Any]) -> str:
    command = action.get("command", "")
    timeout = action.get("timeout", config.get("agent", {}).get("cmd_timeout", 30))
    max_output = config.get("agent", {}).get("cmd_max_output", 8000)

    def _run() -> str:
        proc = subprocess.Popen(
            command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        try:
            stdout_raw, stderr_raw = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.communicate()  # バッファを読み切ってゾンビ化を防ぐ
            return f"[Command timed out after {timeout}s]"

        stdout = stdout_raw[:max_output] if stdout_raw else ""
        stderr = stderr_raw[:max_output] if stderr_raw else ""
        parts = []
        if stdout:
            parts.append(f"STDOUT:\n{stdout}")
        if stderr:
            parts.append(f"STDERR:\n{stderr}")
        parts.append(f"EXIT CODE: {proc.returncode}")
        return "\n".join(parts)

    return await asyncio.to_thread(_run)


async def _file_read(action: dict[str, Any]) -> str:
    path = action.get("path", "")
    async with aiofiles.open(path, encoding="utf-8", errors="replace") as f:
        content = await f.read()
    return content


async def _file_write(action: dict[str, Any]) -> str:
    path = action.get("path", "")
    content = action.get("content", "")
    mode = action.get("mode", "overwrite")

    file_mode = "a" if mode == "append" else "w"
    async with aiofiles.open(path, mode=file_mode, encoding="utf-8") as f:
        await f.write(content)

    return f"Written to {path} ({len(content)} chars, mode={mode})"


async def _dir_list(action: dict[str, Any]) -> str:
    path = action.get("path", ".")

    def _list() -> str:
        p = Path(path)
        if not p.exists():
            return f"Path not found: {path}"
        items = []
        for entry in sorted(p.iterdir()):
            prefix = "[DIR] " if entry.is_dir() else "[FILE]"
            items.append(f"{prefix} {entry.name}")
        return "\n".join(items) if items else "(empty)"

    return await asyncio.to_thread(_list)


async def _clipboard_read() -> str:
    def _read() -> str:
        return pyperclip.paste() or "(empty)"

    return await asyncio.to_thread(_read)


async def _clipboard_write(action: dict[str, Any]) -> str:
    text = action.get("text", "")

    def _write() -> None:
        pyperclip.copy(text)

    await asyncio.to_thread(_write)
    return f"Copied {len(text)} chars to clipboard"


async def _get_processes() -> str:
    def _list() -> str:
        procs = []
        for proc in psutil.process_iter(["pid", "name", "status"]):
            try:
                info = proc.info
                procs.append(f"{info['pid']:6d}  {info['status']:10s}  {info['name']}")
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        return "\n".join(procs[:200])  # 上限200プロセス

    return await asyncio.to_thread(_list)


async def _get_windows() -> str:
    def _list() -> str:
        try:
            import pygetwindow as gw
            windows = gw.getAllTitles()
            titles = [t for t in windows if t.strip()]
            return "\n".join(titles) if titles else "(no windows)"
        except Exception as exc:
            return f"Error: {exc}"

    return await asyncio.to_thread(_list)


async def _get_ui_text(action: dict[str, Any]) -> str:
    window_title = action.get("window", "")

    def _get() -> str:
        try:
            from pywinauto import Desktop
            app = Desktop(backend="uia")
            wins = app.windows(title_re=f".*{window_title}.*") if window_title else app.windows()
            if not wins:
                return f"Window not found: {window_title}"
            win = wins[0]
            texts = win.texts()
            return "\n".join(t for t in texts if t.strip())
        except Exception as exc:
            return f"Error getting UI text: {exc}"

    return await asyncio.to_thread(_get)


async def _get_env(action: dict[str, Any]) -> str:
    key = action.get("key", "")
    if key:
        value = os.environ.get(key, "(not set)")
        return f"{key}={value}"
    # 全環境変数
    return "\n".join(f"{k}={v}" for k, v in sorted(os.environ.items()))


async def _get_sysinfo() -> str:
    def _info() -> str:
        cpu = psutil.cpu_percent(interval=0.5)
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage("C:\\")
        lines = [
            f"CPU Usage:    {cpu:.1f}%",
            f"Memory:       {mem.used / 1024**3:.1f} GB / {mem.total / 1024**3:.1f} GB ({mem.percent:.1f}%)",
            f"Disk (C:):    {disk.used / 1024**3:.1f} GB / {disk.total / 1024**3:.1f} GB ({disk.percent:.1f}%)",
        ]
        return "\n".join(lines)

    return await asyncio.to_thread(_info)


async def _web_fetch(action: dict[str, Any], config: dict[str, Any]) -> str:
    agent_cfg = config.get("agent", {})
    if not agent_cfg.get("web_fetch_enabled", False):
        return "web_fetch is disabled. Enable it in config.yaml (web_fetch_enabled: true)."

    url = action.get("url", "")
    max_chars = agent_cfg.get("web_fetch_max_chars", 12000)
    allowlist: list[str] = agent_cfg.get("web_fetch_allowlist", [])

    if allowlist and not any(url.startswith(a) for a in allowlist):
        return f"URL not in allowlist: {url}"

    import httpx
    import html2text

    async with httpx.AsyncClient(follow_redirects=True, timeout=30) as client:
        resp = await client.get(url, headers={"User-Agent": "Operant/0.2"})
        resp.raise_for_status()
        html = resp.text

    converter = html2text.HTML2Text()
    converter.ignore_links = False
    converter.ignore_images = True
    md = converter.handle(html)

    if len(md) > max_chars:
        md = md[:max_chars] + f"\n\n[Truncated at {max_chars} chars]"

    return md


async def _wait(action: dict[str, Any]) -> str:
    ms = action.get("ms", 1000)
    reason = action.get("reason", "")
    await asyncio.sleep(ms / 1000)
    return f"Waited {ms}ms" + (f" ({reason})" if reason else "")
