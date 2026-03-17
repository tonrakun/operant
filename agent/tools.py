"""
agent/tools.py — テキスト直接処理ツール群
全アクションを execute_action(action: dict) -> str で統一処理
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
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
        elif name == "file_delete":
            return await _file_delete(action)
        elif name == "file_copy":
            return await _file_copy(action)
        elif name == "file_move":
            return await _file_move(action)
        elif name == "dir_list":
            return await _dir_list(action)
        elif name == "file_search":
            return await _file_search(action)
        elif name == "find_in_file":
            return await _find_in_file(action)
        elif name == "clipboard_read":
            return await _clipboard_read()
        elif name == "clipboard_write":
            return await _clipboard_write(action)
        elif name == "get_processes":
            return await _get_processes()
        elif name == "process_kill":
            return await _process_kill(action)
        elif name == "get_windows":
            return await _get_windows()
        elif name == "window_focus":
            return await _window_focus(action)
        elif name == "app_launch":
            return await _app_launch(action)
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
            proc.communicate()
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
    offset = action.get("offset", 0)   # 開始行（0-indexed）
    limit = action.get("limit", 0)     # 読み込み行数（0=全部）
    async with aiofiles.open(path, encoding="utf-8", errors="replace") as f:
        content = await f.read()
    lines = content.splitlines(keepends=True)
    if offset or limit:
        end = offset + limit if limit else len(lines)
        lines = lines[offset:end]
        content = "".join(lines)
        return content + f"\n[Lines {offset+1}-{min(offset+limit, len(lines)) if limit else len(lines)} of {len(content.splitlines())+offset}]"
    return content


async def _file_write(action: dict[str, Any]) -> str:
    path = action.get("path", "")
    content = action.get("content", "")
    mode = action.get("mode", "overwrite")
    # 親ディレクトリが存在しない場合は作成
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    file_mode = "a" if mode == "append" else "w"
    async with aiofiles.open(path, mode=file_mode, encoding="utf-8") as f:
        await f.write(content)
    return f"Written to {path} ({len(content)} chars, mode={mode})"


async def _file_delete(action: dict[str, Any]) -> str:
    path = action.get("path", "")

    def _del() -> str:
        p = Path(path)
        if not p.exists():
            return f"Not found: {path}"
        if p.is_dir():
            shutil.rmtree(p)
            return f"Directory deleted: {path}"
        else:
            p.unlink()
            return f"File deleted: {path}"

    return await asyncio.to_thread(_del)


async def _file_copy(action: dict[str, Any]) -> str:
    src = action.get("src", "")
    dst = action.get("dst", "")

    def _copy() -> str:
        s = Path(src)
        d = Path(dst)
        if not s.exists():
            return f"Source not found: {src}"
        d.parent.mkdir(parents=True, exist_ok=True)
        if s.is_dir():
            shutil.copytree(s, d)
        else:
            shutil.copy2(s, d)
        return f"Copied: {src} → {dst}"

    return await asyncio.to_thread(_copy)


async def _file_move(action: dict[str, Any]) -> str:
    src = action.get("src", "")
    dst = action.get("dst", "")

    def _move() -> str:
        s = Path(src)
        if not s.exists():
            return f"Source not found: {src}"
        Path(dst).parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(s), dst)
        return f"Moved: {src} → {dst}"

    return await asyncio.to_thread(_move)


async def _dir_list(action: dict[str, Any]) -> str:
    path = action.get("path", ".")

    def _list() -> str:
        p = Path(path)
        if not p.exists():
            return f"Path not found: {path}"
        items = []
        for entry in sorted(p.iterdir()):
            prefix = "[DIR] " if entry.is_dir() else "[FILE]"
            size = ""
            if entry.is_file():
                try:
                    size = f" ({entry.stat().st_size:,} bytes)"
                except OSError:
                    pass
            items.append(f"{prefix} {entry.name}{size}")
        return "\n".join(items) if items else "(empty)"

    return await asyncio.to_thread(_list)


async def _file_search(action: dict[str, Any]) -> str:
    path = action.get("path", ".")
    pattern = action.get("pattern", "*")
    recursive = action.get("recursive", False)
    max_results = action.get("max_results", 100)

    def _search() -> str:
        p = Path(path)
        if not p.exists():
            return f"Path not found: {path}"
        if recursive:
            matches = list(p.rglob(pattern))
        else:
            matches = list(p.glob(pattern))
        matches = matches[:max_results]
        if not matches:
            return f"No files matching '{pattern}' in {path}"
        lines = [str(m) for m in sorted(matches)]
        result = "\n".join(lines)
        if len(matches) == max_results:
            result += f"\n[Showing first {max_results} results]"
        return result

    return await asyncio.to_thread(_search)


async def _find_in_file(action: dict[str, Any]) -> str:
    path = action.get("path", "")
    query = action.get("query", "")
    case_sensitive = action.get("case_sensitive", False)
    max_results = action.get("max_results", 50)

    async with aiofiles.open(path, encoding="utf-8", errors="replace") as f:
        content = await f.read()

    lines = content.splitlines()
    matches = []
    q = query if case_sensitive else query.lower()
    for i, line in enumerate(lines, 1):
        haystack = line if case_sensitive else line.lower()
        if q in haystack:
            matches.append(f"Line {i:4d}: {line.rstrip()}")
        if len(matches) >= max_results:
            break

    if not matches:
        return f"'{query}' not found in {path}"
    result = f"Found {len(matches)} match(es) for '{query}' in {path}:\n"
    result += "\n".join(matches)
    if len(matches) == max_results:
        result += f"\n[Showing first {max_results} results]"
    return result


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
        for proc in psutil.process_iter(["pid", "name", "status", "memory_info"]):
            try:
                info = proc.info
                mem_mb = info["memory_info"].rss / 1024 / 1024 if info.get("memory_info") else 0
                procs.append(f"{info['pid']:6d}  {info['status']:10s}  {mem_mb:6.1f}MB  {info['name']}")
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        return "PID     STATUS      MEM      NAME\n" + "\n".join(procs[:200])

    return await asyncio.to_thread(_list)


async def _process_kill(action: dict[str, Any]) -> str:
    pid = action.get("pid")
    name = action.get("name", "")

    def _kill() -> str:
        killed = []
        if pid is not None:
            try:
                p = psutil.Process(int(pid))
                pname = p.name()
                p.kill()
                killed.append(f"PID {pid} ({pname})")
            except psutil.NoSuchProcess:
                return f"Process PID {pid} not found"
            except psutil.AccessDenied:
                return f"Access denied to kill PID {pid}"
        elif name:
            for proc in psutil.process_iter(["pid", "name"]):
                try:
                    if proc.info["name"].lower() == name.lower():
                        proc.kill()
                        killed.append(f"PID {proc.pid} ({proc.info['name']})")
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            if not killed:
                return f"No process named '{name}' found"
        else:
            return "Specify 'pid' or 'name'"
        return f"Killed: {', '.join(killed)}"

    return await asyncio.to_thread(_kill)


async def _get_windows() -> str:
    def _list() -> str:
        try:
            import pygetwindow as gw
            windows = gw.getAllWindows()
            lines = []
            for w in windows:
                if w.title.strip():
                    lines.append(f"[{'visible' if w.visible else 'hidden'}] {w.title}")
            return "\n".join(lines) if lines else "(no windows)"
        except Exception as exc:
            return f"Error: {exc}"

    return await asyncio.to_thread(_list)


async def _window_focus(action: dict[str, Any]) -> str:
    title = action.get("title", "")

    def _focus() -> str:
        try:
            import pygetwindow as gw
            wins = gw.getWindowsWithTitle(title)
            if not wins:
                return f"Window not found: '{title}'"
            w = wins[0]
            if w.isMinimized:
                w.restore()
            w.activate()
            return f"Focused window: '{w.title}'"
        except Exception as exc:
            return f"Error focusing window: {exc}"

    return await asyncio.to_thread(_focus)


async def _app_launch(action: dict[str, Any]) -> str:
    path = action.get("path", "")
    args = action.get("args", [])

    def _launch() -> str:
        try:
            cmd = [path] + [str(a) for a in args]
            proc = subprocess.Popen(cmd, shell=False)
            return f"Launched '{path}' (PID: {proc.pid})"
        except FileNotFoundError:
            # shell=True で再試行（環境変数PATH経由の場合）
            try:
                cmd_str = path + (" " + " ".join(str(a) for a in args) if args else "")
                proc = subprocess.Popen(cmd_str, shell=True)
                return f"Launched '{path}' (PID: {proc.pid})"
            except Exception as exc2:
                return f"Failed to launch '{path}': {exc2}"
        except Exception as exc:
            return f"Failed to launch '{path}': {exc}"

    return await asyncio.to_thread(_launch)


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

    import httpx
    import html2text

    async with httpx.AsyncClient(follow_redirects=True, timeout=30) as client:
        resp = await client.get(url, headers={"User-Agent": "Operant/0.4"})
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
