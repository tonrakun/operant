"""
main.py — Operant エントリーポイント
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import yaml

# ロギング設定
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
)

# ファイルハンドラーは logs/ ディレクトリ作成後に追加
def _setup_file_logger() -> None:
    logs_dir = Path(__file__).parent / "logs"
    logs_dir.mkdir(exist_ok=True)
    from logging.handlers import RotatingFileHandler
    fh = RotatingFileHandler(
        logs_dir / "operant.log",
        maxBytes=5 * 1024 * 1024,  # 5MB
        backupCount=3,
        encoding="utf-8",
    )
    fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
    logging.getLogger().addHandler(fh)


logger = logging.getLogger(__name__)


def _load_config() -> dict:
    config_path = Path(__file__).parent / "config.yaml"
    if not config_path.exists():
        return {}
    with open(config_path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def main() -> None:
    parser = argparse.ArgumentParser(description="Operant — Autonomous Windows Agent")
    parser.add_argument("--setup", action="store_true", help="Run setup wizard")
    args = parser.parse_args()

    config_path = Path(__file__).parent / "config.yaml"

    if args.setup or not config_path.exists():
        if not config_path.exists():
            print("config.yaml not found. Starting setup wizard...")
        from setup import run_setup
        run_setup()
        print()
        print("Setup complete. Run 'python main.py' to start Operant.")
        return

    _setup_file_logger()
    config = _load_config()

    if not config:
        print("ERROR: config.yaml is empty or invalid. Run 'python main.py --setup'.")
        sys.exit(1)

    logger.info("Starting Operant v1.0.0")

    from web.server import run_server
    run_server(config)


if __name__ == "__main__":
    main()
