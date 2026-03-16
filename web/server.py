"""
web/server.py — FastAPI + WebSocket サーバー
パスワード認証・HTTP-only Cookie セッション管理
"""
from __future__ import annotations

import logging
import re
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import bcrypt
import yaml
from fastapi import Cookie, FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).parent / "static"
CHATS_DIR = Path(__file__).parent.parent / "chats"

# インメモリセッション: {token: expires_at (datetime)}
_sessions: dict[str, datetime] = {}


# ---------------------------------------------------------------------------
# アプリ生成
# ---------------------------------------------------------------------------

def create_app(config: dict[str, Any]) -> FastAPI:
    app = FastAPI(title="Operant", docs_url=None, redoc_url=None)

    # エージェントインスタンス初期化
    try:
        from agent.core import AgentCore
        agent = AgentCore(config)
    except Exception as exc:
        logger.error("Failed to initialize AgentCore: %s", exc, exc_info=True)
        raise

    web_cfg = config.get("web", {})
    session_expire_hours: int = web_cfg.get("session_expire_hours", 24)
    password_hash: str = web_cfg.get("password_hash", "")

    # ---------------------------------------------------------------------------
    # 認証ユーティリティ
    # ---------------------------------------------------------------------------

    def _verify_session(token: str | None) -> bool:
        if not token:
            return False
        exp = _sessions.get(token)
        if exp is None:
            return False
        if datetime.now(timezone.utc) > exp:
            del _sessions[token]
            return False
        return True

    def _create_session() -> tuple[str, datetime]:
        token = secrets.token_hex(32)
        exp = datetime.now(timezone.utc) + timedelta(hours=session_expire_hours)
        _sessions[token] = exp
        return token, exp

    # チャット履歴（インメモリ）
    _chat_history: list[dict[str, Any]] = []

    def _save_msg(msg: dict[str, Any]) -> None:
        if msg.get("type") in ("think", "done", "error", "user"):
            _chat_history.append({"type": msg["type"], "content": msg.get("content", "")})

    # ---------------------------------------------------------------------------
    # i18n API
    # ---------------------------------------------------------------------------

    @app.get("/api/i18n")
    async def get_i18n() -> JSONResponse:
        lang = config.get("language", "en")
        i18n_path = Path(__file__).parent.parent / "i18n" / f"{lang}.yaml"
        if not i18n_path.exists():
            i18n_path = Path(__file__).parent.parent / "i18n" / "en.yaml"
        with open(i18n_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return JSONResponse(data)

    # ---------------------------------------------------------------------------
    # チャット履歴 API
    # ---------------------------------------------------------------------------

    @app.get("/api/history")
    async def get_history(session: str | None = Cookie(default=None)) -> JSONResponse:
        if not _verify_session(session):
            raise HTTPException(status_code=401)
        return JSONResponse(_chat_history)

    @app.post("/api/history/clear")
    async def clear_history(session: str | None = Cookie(default=None)) -> JSONResponse:
        if not _verify_session(session):
            raise HTTPException(status_code=401)
        _chat_history.clear()
        return JSONResponse({"ok": True})

    # ---------------------------------------------------------------------------
    # 保存チャット API
    # ---------------------------------------------------------------------------

    _CHAT_ID_RE = re.compile(r"^\d{8}_\d{6}$")  # パストラバーサル防止

    @app.get("/api/chats")
    async def list_saved_chats(session: str | None = Cookie(default=None)) -> JSONResponse:
        if not _verify_session(session):
            raise HTTPException(status_code=401)
        CHATS_DIR.mkdir(exist_ok=True)
        chats = []
        for f in sorted(CHATS_DIR.glob("*.yaml"), reverse=True):
            try:
                with open(f, encoding="utf-8") as fh:
                    data = yaml.safe_load(fh)
                chats.append({
                    "id": data["id"],
                    "title": data.get("title", "Chat"),
                    "created_at": data["created_at"],
                    "message_count": len(data.get("messages", [])),
                })
            except Exception:
                pass
        return JSONResponse(chats)

    @app.get("/api/chats/{chat_id}")
    async def get_saved_chat(
        chat_id: str,
        session: str | None = Cookie(default=None),
    ) -> JSONResponse:
        if not _verify_session(session):
            raise HTTPException(status_code=401)
        if not _CHAT_ID_RE.match(chat_id):
            raise HTTPException(status_code=400, detail="Invalid chat ID")
        chat_file = CHATS_DIR / f"{chat_id}.yaml"
        if not chat_file.exists():
            raise HTTPException(status_code=404)
        with open(chat_file, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return JSONResponse(data)

    @app.post("/api/chats")
    async def save_current_chat(
        request: Request,
        session: str | None = Cookie(default=None),
    ) -> JSONResponse:
        if not _verify_session(session):
            raise HTTPException(status_code=401)
        if not _chat_history:
            raise HTTPException(status_code=400, detail="No messages to save")
        CHATS_DIR.mkdir(exist_ok=True)

        body = await request.json()
        title: str = body.get("title", "").strip()
        if not title:
            for msg in _chat_history:
                if msg["type"] == "user":
                    title = msg["content"][:50]
                    break
        if not title:
            title = "Chat"

        chat_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        data = {
            "id": chat_id,
            "title": title,
            "created_at": datetime.now().isoformat(),
            "messages": [m for m in _chat_history],  # 画像は含まれない（テキストのみ）
        }
        chat_file = CHATS_DIR / f"{chat_id}.yaml"
        with open(chat_file, "w", encoding="utf-8") as f:
            yaml.dump(data, f, allow_unicode=True, default_flow_style=False)

        return JSONResponse({"id": chat_id, "title": title})

    @app.delete("/api/chats/{chat_id}")
    async def delete_saved_chat(
        chat_id: str,
        session: str | None = Cookie(default=None),
    ) -> JSONResponse:
        if not _verify_session(session):
            raise HTTPException(status_code=401)
        if not _CHAT_ID_RE.match(chat_id):
            raise HTTPException(status_code=400, detail="Invalid chat ID")
        chat_file = CHATS_DIR / f"{chat_id}.yaml"
        if chat_file.exists():
            chat_file.unlink()
        return JSONResponse({"ok": True})

    # ---------------------------------------------------------------------------
    # 認証エンドポイント
    # ---------------------------------------------------------------------------

    @app.get("/login")
    async def login_page() -> FileResponse:
        return FileResponse(STATIC_DIR / "login.html")

    @app.post("/api/login")
    async def do_login(request: Request) -> JSONResponse:
        body = await request.json()
        password: str = body.get("password", "")
        if not password_hash:
            raise HTTPException(status_code=500, detail="Password not configured")

        if not bcrypt.checkpw(password.encode(), password_hash.encode()):
            raise HTTPException(status_code=401, detail="Invalid password")

        token, exp = _create_session()
        response = JSONResponse({"ok": True})
        response.set_cookie(
            key="session",
            value=token,
            httponly=True,
            samesite="strict",
            expires=int(exp.timestamp()),
        )
        return response

    @app.post("/api/logout")
    async def do_logout(session: str | None = Cookie(default=None)) -> JSONResponse:
        if session and session in _sessions:
            del _sessions[session]
        response = JSONResponse({"ok": True})
        response.delete_cookie("session")
        return response

    # ---------------------------------------------------------------------------
    # メインページ
    # ---------------------------------------------------------------------------

    @app.get("/", response_model=None)
    async def index(session: str | None = Cookie(default=None)) -> FileResponse | RedirectResponse:
        if not _verify_session(session):
            return RedirectResponse("/login")
        return FileResponse(STATIC_DIR / "index.html")

    # ---------------------------------------------------------------------------
    # エージェント API
    # ---------------------------------------------------------------------------

    @app.get("/api/status")
    async def status(session: str | None = Cookie(default=None)) -> JSONResponse:
        if not _verify_session(session):
            raise HTTPException(status_code=401)
        return JSONResponse({"running": agent.is_running()})

    @app.post("/api/stop")
    async def stop(session: str | None = Cookie(default=None)) -> JSONResponse:
        if not _verify_session(session):
            raise HTTPException(status_code=401)
        agent.emergency_stop()
        return JSONResponse({"ok": True})

    # ---------------------------------------------------------------------------
    # WebSocket
    # ---------------------------------------------------------------------------

    @app.websocket("/ws")
    async def websocket_endpoint(
        websocket: WebSocket,
        session: str | None = Cookie(default=None),
    ) -> None:
        if not _verify_session(session):
            await websocket.close(code=4401)
            return

        await websocket.accept()
        logger.info("WebSocket connected")

        async def send(msg: dict[str, Any]) -> None:
            _save_msg(msg)
            try:
                await websocket.send_json(msg)
            except Exception:
                pass

        try:
            while True:
                data = await websocket.receive_json()
                msg_type = data.get("type", "")

                if msg_type == "task":
                    user_input: str = data.get("content", "").strip()
                    if user_input:
                        _save_msg({"type": "user", "content": user_input})
                        await agent.start_task(user_input, send)

                elif msg_type == "stop":
                    agent.emergency_stop()
                    await send({"type": "log", "content": "Stop requested"})

        except WebSocketDisconnect:
            logger.info("WebSocket disconnected")
        except Exception as exc:
            logger.error("WebSocket error: %s", exc, exc_info=True)

    # ---------------------------------------------------------------------------
    # 静的ファイル（最後に登録）
    # ---------------------------------------------------------------------------
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    return app


# ---------------------------------------------------------------------------
# サーバー起動
# ---------------------------------------------------------------------------

def run_server(config: dict[str, Any]) -> None:
    import uvicorn

    app = create_app(config)
    web_cfg = config.get("web", {})
    host = web_cfg.get("host", "0.0.0.0")
    port = web_cfg.get("port", 8765)

    # uvicorn の起動メッセージ中の "0.0.0.0" を "localhost" に書き換えるフィルター
    if host == "0.0.0.0":
        import logging as _logging

        class _LocalhostFilter(_logging.Filter):
            def filter(self, record: _logging.LogRecord) -> bool:
                if isinstance(record.msg, str):
                    record.msg = record.msg.replace(f"0.0.0.0:{port}", f"localhost:{port}")
                if isinstance(record.args, (tuple, list)):
                    record.args = tuple(
                        str(a).replace(f"0.0.0.0:{port}", f"localhost:{port}")
                        if isinstance(a, str) else a
                        for a in record.args
                    )
                return True

        _logging.getLogger("uvicorn.error").addFilter(_LocalhostFilter())

    # LAN IPアドレスを取得して表示（デフォルトルート経由のインターフェースを使用）
    import socket
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as _s:
            _s.connect(("8.8.8.8", 80))
            lan_ip = _s.getsockname()[0]
    except Exception:
        lan_ip = None

    logger.info("=" * 52)
    logger.info("  Operant is running!")
    logger.info("  This PC  : http://localhost:%d", port)
    if host == "0.0.0.0" and lan_ip and not lan_ip.startswith("127."):
        logger.info("  LAN      : http://%s:%d", lan_ip, port)
        logger.info("  (Windows Firewall may need to allow port %d)", port)
    logger.info("=" * 52)
    uvicorn.run(app, host=host, port=port, log_level="info")
