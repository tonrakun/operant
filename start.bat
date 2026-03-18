@echo off
chcp 65001 >nul
setlocal

:: 仮想環境の確認
if not exist ".venv\Scripts\python.exe" (
    echo  [エラー] 仮想環境が見つかりません。
    echo  先に install.bat を実行してください。
    pause
    exit /b 1
)

:: config.yaml の確認
if not exist "config.yaml" (
    echo  config.yaml が見つかりません。セットアップウィザードを起動します。
    echo.
    .venv\Scripts\python main.py --setup
    echo.
)

:: Operant 起動
.venv\Scripts\python main.py
