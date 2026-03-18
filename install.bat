@echo off
chcp 65001 >nul
setlocal

echo.
echo  ╔══════════════════════════════════════╗
echo  ║        Operant  インストーラー        ║
echo  ╚══════════════════════════════════════╝
echo.

:: ── Python 確認 ────────────────────────────────────────────────
where python >nul 2>&1
if errorlevel 1 (
    echo  [エラー] Python が見つかりません。
    echo.
    echo  Python 3.11 以上をインストールしてください:
    echo    https://www.python.org/downloads/
    echo.
    echo  インストール時に "Add Python to PATH" にチェックを入れてください。
    pause
    exit /b 1
)

:: Python バージョン確認（3.11 以上必須）
for /f "tokens=2 delims= " %%v in ('python --version 2^>^&1') do set PY_VER=%%v
for /f "tokens=1,2 delims=." %%a in ("%PY_VER%") do (
    set PY_MAJOR=%%a
    set PY_MINOR=%%b
)
if %PY_MAJOR% LSS 3 (
    echo  [エラー] Python %PY_VER% は非対応です。Python 3.11 以上が必要です。
    echo    https://www.python.org/downloads/
    pause
    exit /b 1
)
if %PY_MAJOR% EQU 3 if %PY_MINOR% LSS 11 (
    echo  [エラー] Python %PY_VER% は非対応です。Python 3.11 以上が必要です。
    echo    https://www.python.org/downloads/
    pause
    exit /b 1
)
echo  [OK] Python %PY_VER% を検出しました。

:: ── 仮想環境の作成 ─────────────────────────────────────────────
if not exist ".venv\" (
    echo  [1/3] 仮想環境を作成中...
    python -m venv .venv
    if errorlevel 1 (
        echo  [エラー] 仮想環境の作成に失敗しました。
        pause
        exit /b 1
    )
    echo  [OK] 仮想環境を作成しました。
) else (
    echo  [OK] 既存の仮想環境が見つかりました。
)

:: ── 依存パッケージのインストール ───────────────────────────────
echo  [2/3] 依存パッケージをインストール中（初回は数分かかります）...
.venv\Scripts\pip install --upgrade pip >nul 2>&1
.venv\Scripts\pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo  [エラー] インストールに失敗しました。
    echo.
    echo  よくある原因:
    echo    - Microsoft C++ Build Tools が不足している場合は以下からインストール:
    echo      https://visualstudio.microsoft.com/visual-cpp-build-tools/
    echo      （「C++ によるデスクトップ開発」を選択してください）
    echo    - インストール後にターミナルを再起動して、このファイルを再実行してください。
    pause
    exit /b 1
)
echo  [OK] パッケージのインストールが完了しました。

:: ── セットアップウィザード起動 ─────────────────────────────────
echo  [3/3] セットアップウィザードを起動します...
echo.
.venv\Scripts\python main.py

echo.
echo  セットアップが完了しました。
echo  次回からは start.bat をダブルクリックして起動してください。
echo.
pause
