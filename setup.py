"""
setup.py — Operant CLIセットアップウィザード
"""
from __future__ import annotations

import getpass
import locale
import os
import sys
from pathlib import Path
from typing import Any

import bcrypt
import yaml


# ---------------------------------------------------------------------------
# i18n ユーティリティ
# ---------------------------------------------------------------------------

def _load_i18n(lang: str) -> dict[str, Any]:
    path = Path(__file__).parent / "i18n" / f"{lang}.yaml"
    if not path.exists():
        path = Path(__file__).parent / "i18n" / "en.yaml"
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _t(resources: dict[str, Any], key: str, **kwargs: Any) -> str:
    """ドット区切りキーでi18nリソースを引く"""
    parts = key.split(".")
    val: Any = resources
    for p in parts:
        if isinstance(val, dict):
            val = val.get(p, key)
        else:
            return key
    text = str(val)
    if kwargs:
        text = text.format(**kwargs)
    return text


# ---------------------------------------------------------------------------
# 接続テスト
# ---------------------------------------------------------------------------

def _test_anthropic(api_key: str) -> None:
    import anthropic
    client = anthropic.Anthropic(api_key=api_key)
    client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1,
        messages=[{"role": "user", "content": "hi"}],
    )


def _test_openai(api_key: str, base_url: str | None = None) -> None:
    import openai
    kwargs: dict[str, Any] = {"api_key": api_key}
    if base_url:
        kwargs["base_url"] = base_url
    client = openai.OpenAI(**kwargs)
    client.chat.completions.create(
        model="gpt-4o-mini",
        max_tokens=1,
        messages=[{"role": "user", "content": "hi"}],
    )


def _test_azure(api_key: str, endpoint: str, deployment: str) -> None:
    import openai
    client = openai.AzureOpenAI(
        api_key=api_key,
        azure_endpoint=endpoint,
        api_version="2024-02-01",
    )
    client.chat.completions.create(
        model=deployment,
        max_tokens=1,
        messages=[{"role": "user", "content": "hi"}],
    )


def _test_gemini(api_key: str) -> None:
    from google import genai
    client = genai.Client(api_key=api_key)
    client.models.generate_content(
        model="gemini-2.0-flash",
        contents="hi",
    )


def _test_ollama(base_url: str, model: str) -> None:
    import openai
    client = openai.OpenAI(
        api_key="ollama",
        base_url=f"{base_url}/v1",
    )
    client.chat.completions.create(
        model=model,
        max_tokens=1,
        messages=[{"role": "user", "content": "hi"}],
    )


def _run_connection_test(
    provider: str,
    api_key: str,
    azure_endpoint: str = "",
    azure_deployment: str = "",
    ollama_base_url: str = "",
    ollama_model: str = "",
) -> None:
    if provider == "claude":
        _test_anthropic(api_key)
    elif provider == "openai":
        _test_openai(api_key)
    elif provider == "azure_openai":
        _test_azure(api_key, azure_endpoint, azure_deployment)
    elif provider == "gemini":
        _test_gemini(api_key)
    elif provider == "ollama":
        _test_ollama(ollama_base_url, ollama_model)


# ---------------------------------------------------------------------------
# OPERANT.md テンプレート生成
# ---------------------------------------------------------------------------

def _generate_operant_md(lang: str) -> str:
    if lang == "ja":
        return """\
# Operant Rules

## 基本ルール
- 必ずTHINK:で始め、1〜2文で状況・意図を簡潔に述べる
- 操作が必要なときのみACT:を添える
- タスク完了時はDONE:で締める
- 余計な説明・謝罪・前置きは不要

## ツール選択優先順位
1. テキスト直接取得ツール（file_read, cmd, get_windows等）で完結できるか確認
2. 無理なら Accessibility API（get_ui_text）でUI要素テキスト取得を試みる
3. それも無理ならスクショ（screenshot）経由にフォールバック
4. UIの視覚確認が必要な場合のみ screenshot アクションをリクエストすること

## 禁止操作
- システムファイル（C:\\Windows 以下）の書き込み・削除
- レジストリの書き込み
- ネットワーク設定の変更

## 応答言語
- ユーザーへの返答は日本語で行う

## カスタムルール（自由に追記してください）
"""
    else:
        return """\
# Operant Rules

## Basic Rules
- Always start with THINK: and describe the situation/intent in 1-2 sentences
- Only add ACT: when an action is required
- End with DONE: when the task is complete
- No unnecessary explanations, apologies, or preambles

## Tool Selection Priority
1. Check if text-based tools (file_read, cmd, get_windows, etc.) can handle the task
2. If not, try Accessibility API (get_ui_text) to get UI element text
3. Fall back to screenshot only if the above don't work
4. Only request the screenshot action when visual confirmation of the UI is needed

## Prohibited Actions
- Writing/deleting system files (under C:\\Windows)
- Writing to the registry
- Modifying network settings

## Response Language
- Respond to the user in English

## Custom Rules (add your own below)
"""


# ---------------------------------------------------------------------------
# config.yaml 生成
# ---------------------------------------------------------------------------

def _generate_config(
    lang: str,
    provider: str,
    api_key: str,
    password_hash: str,
    azure_endpoint: str = "",
    azure_deployment: str = "",
    ollama_base_url: str = "",
    ollama_model: str = "",
) -> dict[str, Any]:
    # モデルのデフォルト
    model_defaults = {
        "claude": "claude-opus-4-6",
        "openai": "gpt-4o",
        "azure_openai": azure_deployment or "gpt-4o",
        "gemini": "gemini-2.0-flash",
        "ollama": ollama_model or "llava",
    }

    config: dict[str, Any] = {
        "language": lang,
        "llm": {
            "provider": provider,
            "model": model_defaults.get(provider, "claude-opus-4-6"),
            "max_tokens": 256,
        },
        "api_keys": {
            "anthropic": "${ANTHROPIC_API_KEY}",
            "openai": "${OPENAI_API_KEY}",
            "gemini": "${GEMINI_API_KEY}",
        },
        "screenshot": {
            "max_width": 1280,
            "max_height": 720,
            "quality": 80,
            "format": "webp",
            "diff_threshold": 0.97,
            "capture_delay_ms": 500,
        },
        "agent": {
            "loop_timeout": 300,
            "cmd_timeout": 30,
            "cmd_max_output": 8000,
            "confirm_before_act": False,
            "web_fetch_enabled": False,
            "web_fetch_max_chars": 12000,
        },
        "web": {
            "host": "0.0.0.0",
            "port": 8765,
            "session_expire_hours": 24,
            "password_hash": password_hash,
            "context_history": 10,
        },
    }

    # プロバイダー固有の設定を直接APIキーとして書き込む（環境変数参照を推奨するが、
    # セットアップ時に入力されたキーを直接保存することも選択肢として残す）
    if provider == "claude":
        config["api_keys"]["anthropic"] = api_key
    elif provider in ("openai", "azure_openai"):
        config["api_keys"]["openai"] = api_key
        if provider == "azure_openai":
            config["llm"]["azure_endpoint"] = azure_endpoint
            config["llm"]["azure_deployment"] = azure_deployment
    elif provider == "gemini":
        config["api_keys"]["gemini"] = api_key
    elif provider == "ollama":
        config["llm"]["ollama_base_url"] = ollama_base_url or "http://localhost:11434"

    return config


# ---------------------------------------------------------------------------
# メインウィザード
# ---------------------------------------------------------------------------

def run_setup() -> None:
    """対話形式のセットアップウィザードを実行する"""
    # まず言語選択（デフォルトでja/enのリソースを使う）
    ja = _load_i18n("ja")
    en = _load_i18n("en")

    print()
    print(_t(ja, "setup.welcome"))
    print(_t(ja, "setup.select_language"))
    print(_t(ja, "setup.lang_option_ja"))
    print(_t(ja, "setup.lang_option_en"))
    print("  [3] 中文（简体）")
    print("  [4] 한국어")
    lang_input = input(_t(ja, "setup.lang_prompt")).strip()

    if lang_input == "2":
        lang = "en"
    elif lang_input == "1":
        lang = "ja"
    elif lang_input == "3":
        lang = "zh"
    elif lang_input == "4":
        lang = "ko"
    else:
        # OSロケールを使う
        try:
            loc = locale.getdefaultlocale()[0] or ""
            if loc.startswith("ja"):
                lang = "ja"
            elif loc.startswith("zh"):
                lang = "zh"
            elif loc.startswith("ko"):
                lang = "ko"
            else:
                lang = "en"
        except Exception:
            lang = "en"

    t = _load_i18n(lang)

    def p(key: str, **kwargs: Any) -> str:
        return _t(t, key, **kwargs)

    # [1/5] プロバイダー選択
    print()
    print(p("setup.step_provider"))
    print(p("setup.provider_claude"))
    print(p("setup.provider_openai"))
    print(p("setup.provider_azure"))
    print(p("setup.provider_gemini"))
    # Ollama オプション（i18n キーがない言語ではフォールバック）
    ollama_label = _t(t, "setup.provider_ollama")
    if ollama_label == "setup.provider_ollama":
        ollama_label = "[5] Ollama (Local LLM)"
    print(ollama_label)

    provider_map = {"1": "claude", "2": "openai", "3": "azure_openai", "4": "gemini", "5": "ollama"}
    while True:
        prov_input = input(p("setup.provider_prompt")).strip()
        if prov_input in provider_map:
            provider = provider_map[prov_input]
            break
        print("  Invalid choice. Please enter 1-5.")

    # [2/5] APIキー & プロバイダー固有設定
    print()
    azure_endpoint = ""
    azure_deployment = ""
    ollama_base_url = ""
    ollama_model = ""
    api_key = ""

    if provider == "ollama":
        # Ollama は API キー不要
        base_url_prompt = _t(t, "setup.ollama_base_url_prompt")
        if base_url_prompt == "setup.ollama_base_url_prompt":
            base_url_prompt = "Ollama base URL (default: http://localhost:11434): "
        model_prompt = _t(t, "setup.ollama_model_prompt")
        if model_prompt == "setup.ollama_model_prompt":
            model_prompt = "Model name (default: llava): "
        ollama_base_url = input(base_url_prompt).strip() or "http://localhost:11434"
        ollama_model = input(model_prompt).strip() or "llava"
        while True:
            # [3/5] 接続テスト
            print()
            print(p("setup.step_test"))
            try:
                _run_connection_test(provider, api_key, ollama_base_url=ollama_base_url, ollama_model=ollama_model)
                print(p("setup.test_ok"))
                break
            except Exception as exc:
                print(p("setup.test_fail", error=str(exc)))
                retry = input("Retry? [y/N]: ").strip().lower()
                if retry != "y":
                    break
    else:
        print(p("setup.step_apikey"))

        if provider == "azure_openai":
            azure_endpoint = input(p("setup.azure_endpoint_prompt")).strip()
            azure_deployment = input(p("setup.azure_deployment_prompt")).strip()

        while True:
            api_key = getpass.getpass(p("setup.apikey_prompt"))

            # [3/5] 接続テスト
            print()
            print(p("setup.step_test"))
            try:
                _run_connection_test(provider, api_key, azure_endpoint, azure_deployment)
                print(p("setup.test_ok"))
                break
            except Exception as exc:
                print(p("setup.test_fail", error=str(exc)))
                print(p("setup.test_retry"))

    # [4/5] パスワード設定
    print()
    print(p("setup.step_password"))
    while True:
        pw1 = getpass.getpass(p("setup.password_prompt"))
        if len(pw1) < 8:
            print(p("setup.password_too_short"))
            continue
        pw2 = getpass.getpass(p("setup.password_confirm_prompt"))
        if pw1 != pw2:
            print(p("setup.password_mismatch"))
            continue
        break

    password_hash = bcrypt.hashpw(pw1.encode(), bcrypt.gensalt()).decode()

    # config.yaml 書き込み
    config = _generate_config(
        lang=lang,
        provider=provider,
        api_key=api_key,
        password_hash=password_hash,
        azure_endpoint=azure_endpoint,
        azure_deployment=azure_deployment,
        ollama_base_url=ollama_base_url,
        ollama_model=ollama_model,
    )
    config_path = Path(__file__).parent / "config.yaml"
    with open(config_path, "w", encoding="utf-8") as f:
        yaml.dump(config, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

    # OPERANT.md 書き込み
    operant_path = Path(__file__).parent / "OPERANT.md"
    operant_path.write_text(_generate_operant_md(lang), encoding="utf-8")

    # logs/ ディレクトリ作成
    logs_dir = Path(__file__).parent / "logs"
    logs_dir.mkdir(exist_ok=True)

    # [5/5] 完了
    print()
    print(p("setup.step_done"))
    print(f"  {p('setup.config_saved')}")
    print(f"  {p('setup.operant_saved')}")
    print(f"  {p('setup.start_hint')}")
    print()


if __name__ == "__main__":
    run_setup()
