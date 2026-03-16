# Operant — 要件定義・企画書

> LLMがスクショを見ながらWindowsを自律操作するローカルエージェント

**バージョン:** 0.2.0-draft  
**作成日:** 2026-03-16

---

## 1. プロジェクト概要

### 1.1 コンセプト

ユーザーがWebパネル上でチャット形式の指示を出すと、LLMがスクリーンショットを確認しながらWindowsを自律操作するローカルエージェントツール。ほぼ自分用のオープンソースツールとして設計し、シンプルさ・拡張性・プライバシーを重視する。

### 1.2 基本方針

- **ローカル完結:** LLM API呼び出し以外の通信は一切行わない
- **ローカルネットワーク限定:** WebパネルはLAN内のみアクセス可能、外部公開なし
- **プライバシー優先:** 学習利用なしのAPIを推奨・明示
- **シンプルな依存関係:** セットアップの敷居を下げる
- **Windows専用:** 初期バージョンはWindowsのみ対応
- **多言語対応:** UIをセットアップ時に指定した言語で表示。未指定時はOSのロケールに従う

---

## 2. 機能要件

### 2.1 CLIセットアップ（初回起動時）

オープンソースとして配布するため、初回起動時にCLIウィザードでインタラクティブにセットアップを完了させる。設定完了後は `config.yaml` と `OPERANT.md` が生成される。

#### セットアップ項目（順番に対話形式で進む）

```
Welcome to Operant Setup!
言語を選択してください / Select language:
  [1] 日本語（デフォルト: OS設定）
  [2] English
  > _

--- 以降は選択言語で表示 ---

[1/5] LLMプロバイダーを選択してください:
  [1] Anthropic Claude（推奨: 学習利用なし）
  [2] OpenAI GPT-4o（opt-out推奨）
  [3] Azure OpenAI
  [4] Google Gemini
  > _

[2/5] APIキーを入力してください:
  > _（入力は非表示）

[3/5] 接続テストを実行します... ✓ OK

[4/5] Webパネルのパスワードを設定してください:
  パスワード     > _（入力は非表示）
  パスワード確認 > _（入力は非表示）

[5/5] セットアップ完了！
  設定ファイル: config.yaml
  LLMルール定義: OPERANT.md（編集でエージェントの挙動をカスタマイズ可能）
  起動: python main.py
```

#### 補足仕様

- APIキーはセットアップ時に接続テストを実行し、失敗したらその場で再入力を促す
- パスワードはbcryptでハッシュ化して `config.yaml` に保存（平文保存禁止）
- 言語未選択（Enter スキップ）時は `locale.getdefaultlocale()` でOSのロケールを自動取得
- セットアップ済みの場合は `python main.py --setup` で再実行可能
- 対応言語は初期バージョンでは日本語・英語の2言語

### 2.2 多言語化対応

#### 対象範囲

| 対象 | 詳細 |
|------|------|
| CLIセットアップ | セットアップウィザードの全テキスト |
| Webパネル UI | ボタン・ラベル・メッセージ・エラー表示 |
| エージェントのTHINK/DONE発言 | システムプロンプトで使用言語を指示 |

#### 実装方針

- 翻訳リソースは `i18n/<言語コード>.yaml` で管理（例: `i18n/ja.yaml`, `i18n/en.yaml`）
- バックエンド・フロントエンド両方で同じリソースファイルを参照
- 言語設定は `config.yaml` の `language` フィールドに保存
- 言語コードは BCP 47 準拠（例: `ja`, `en`）

```
operant/
└── i18n/
    ├── ja.yaml   # 日本語
    └── en.yaml   # 英語
```

### 2.3 Webパネル認証

#### 仕様

- パスワード認証のみ（ユーザー名なし）
- セッショントークンをHTTP-only Cookieで管理
- 未認証アクセスはログインページへリダイレクト
- パスワードはbcryptハッシュ化して `config.yaml` に保存
- セッション有効期限は設定ファイルで変更可能（デフォルト: 24時間）
- パスワード変更は `python main.py --setup` で再セットアップ

#### ログインページ

- パスワード入力フォームのみのシンプルな画面
- 誤入力時はエラーメッセージ表示（連続失敗回数の制限は任意実装）

### 2.4 PC自律操作

| 機能 | 詳細 |
|------|------|
| スクリーンショット取得 | mss で高速キャプチャ、WebP圧縮してLLMへ送信 |
| マウス操作 | クリック（左・右・ダブル）、ドラッグ、スクロール |
| キーボード操作 | テキスト入力、キー押下、ショートカット |
| アプリ起動 | プロセス名・パス指定で起動 |
| ウィンドウ操作 | フォーカス、最大化・最小化、ウィンドウ一覧取得 |
| コマンド実行 | cmd / PowerShell コマンドを実行し stdout/stderr をテキストで返す |

### 2.5 テキスト直接処理ツール（スクショ不要）

スクショ経由よりトークン効率・精度が高いため、以下は専用ツールで処理する。

| ツール | アクション | 詳細 |
|--------|-----------|------|
| ファイル読み込み | `file_read` | .txt .md .py .json .csv 等のテキストファイルを直接読み込んでLLMへ渡す |
| ファイル書き込み | `file_write` | 指定パスへテキスト書き込み・上書き・追記 |
| ディレクトリ一覧 | `dir_list` | 指定ディレクトリのファイル・フォルダ一覧取得 |
| コマンド実行 | `cmd` | コマンド実行、stdout/stderr/終了コードをテキスト返却 |
| クリップボード読み取り | `clipboard_read` | クリップボード内容を取得（アプリからコピーした内容も取得可） |
| クリップボード書き込み | `clipboard_write` | クリップボードへテキストを書き込む |
| プロセス一覧 | `get_processes` | 実行中プロセスの一覧取得 |
| ウィンドウ一覧 | `get_windows` | 開いているウィンドウのタイトル一覧取得 |
| UIテキスト取得 | `get_ui_text` | Windows Accessibility API（pywinauto）経由でUI要素のテキストを直接取得 |
| 環境変数取得 | `get_env` | 指定の環境変数を取得 |
| システム情報 | `get_sysinfo` | CPU・メモリ・ディスク使用率等を取得 |
| Webドキュメント取得 | `web_fetch` | URLのHTMLをMarkdown変換してLLMへ渡す。エラー発生時の公式ドキュメント・スタックオーバーフロー等の参照を想定。**オプション機能（configで有効化）**。外部通信が発生するためローカル完結方針の例外扱い |

**ツール選択の優先順位:**

1. テキスト直接取得ツールで完結できるか確認
2. 無理なら Accessibility API（`get_ui_text`）でUI要素テキスト取得を試みる
3. それも無理ならスクショ経由にフォールバック

### 2.6 Webパネル（チャットUI）

#### レイアウト（2ペイン構成）

**左ペイン: LIVEスクショビュー**

- 最新スクリーンショットを常に1枚表示（新しいものが来たら差し替え）
- エージェント動作中は「LIVE」バッジ表示
- 停止中は最後のスクショをそのまま保持
- クリックで拡大表示

**右ペイン: チャット**

- ユーザー発言・LLMのTHINK発言・DONE通知を時系列表示
- ACT行（操作JSON）はチャットに出さず実行ログへ格納
- 下部にテキスト入力欄
- 緊急停止ボタンを右ペイン上部に常設

#### メッセージ出し分けルール

| 種別 | チャット表示 | ログ記録 | LIVEビュー |
|------|------------|---------|-----------|
| ユーザー入力 | ✓ | ✓ | — |
| THINK: 行 | ✓ | ✓ | — |
| ACT: 行 | — | ✓（JSON） | — |
| DONE: 行 | ✓ | ✓ | — |
| スクショ | — | — | ✓（差し替え） |
| エラー・リトライ | — | ✓ | — |

#### アクセス制限

- ローカルネットワーク内のみアクセス可能
- 外部公開（ngrok等）は非推奨・ドキュメントに明記

### 2.7 LLMマルチプロバイダー

抽象基底クラスで統一インターフェースを持ち、設定ファイルで使用LLMを切り替え可能。

| プロバイダー | SDK | 学習利用 | 備考 |
|------------|-----|---------|------|
| Anthropic Claude | anthropic | デフォルト対象外 | **第一推奨** |
| OpenAI GPT-4o | openai | opt-out設定推奨 | 第二推奨 |
| Azure OpenAI | openai | エンタープライズ契約で保護 | 企業向け推奨 |
| Google Gemini | google-genai | DPA締結で保護 | 第三推奨 |

全プロバイダーでVision（画像入力）対応が必須条件。

---

## 3. LLM入出力設計

### 3.1 出力フォーマット（構造化テキスト方式）

JSON強制をやめ、THINK / ACT / DONE の3プレフィックスで構造化する。会話と操作を自然に共存させる。

```
THINK: <状況・意図を1〜2文で簡潔に記述>
ACT: {"action":"<アクション名>", ...パラメータ}
```

```
THINK: 保存先フォルダを確認したい。どこに保存しますか？
```

```
DONE: ファイルをデスクトップに保存しました。
```

| パターン | 用途 |
|---------|------|
| THINK のみ | 会話・質問・確認（操作なし） |
| THINK + ACT | 操作実行（通常のエージェント動作） |
| DONE のみ | タスク完了通知 |

### 3.2 ACTアクション一覧

```jsonc
// マウス・キーボード操作
{"action": "click",        "x": 320, "y": 450}
{"action": "double_click", "x": 320, "y": 450}
{"action": "right_click",  "x": 320, "y": 450}
{"action": "drag",         "x1": 100, "y1": 100, "x2": 400, "y2": 400}
{"action": "scroll",       "x": 500, "y": 300, "dir": "down", "amount": 3}
{"action": "type",         "text": "hello world"}
{"action": "key",          "key": "enter"}

// テキスト直接処理
{"action": "cmd",            "command": "dir C:\\Users", "timeout": 30}
{"action": "file_read",      "path": "C:/foo.txt"}
{"action": "file_write",     "path": "C:/foo.txt", "content": "...", "mode": "overwrite"}
{"action": "dir_list",       "path": "C:/project"}
{"action": "clipboard_read"}
{"action": "clipboard_write","text": "..."}
{"action": "get_windows"}
{"action": "get_processes"}
{"action": "get_ui_text",    "window": "Notepad"}
{"action": "get_env",        "key": "PATH"}
{"action": "get_sysinfo"}

// スクリーンショット（LLMが必要と判断したときのみリクエスト）
{"action": "screenshot"}

// Webドキュメント取得（オプション機能・要設定有効化）
{"action": "web_fetch", "url": "https://example.com/docs"}

// 制御
{"action": "wait",   "reason": "ロード待ち", "ms": 1000}
{"action": "done",   "summary": "完了内容を1行で"}
```

### 3.3 OPERANT.md — LLMルール定義ファイル

エージェントの挙動をユーザーがテキストで自由にカスタマイズできるファイル。セットアップ時に自動生成され、システムプロンプトの末尾にそのまま追記される。

#### セットアップ時の自動生成内容（テンプレート）

```markdown
# Operant Rules

## 基本ルール
- 必ずTHINK:で始め、1〜2文で状況・意図を簡潔に述べる
- 操作が必要なときのみACT:を添える
- タスク完了時はDONE:で締める
- 余計な説明・謝罪・前置きは不要

## 禁止操作
- システムファイル（C:\Windows 以下）の書き込み・削除
- レジストリの書き込み
- ネットワーク設定の変更

## 応答言語
- ユーザーへの返答は日本語で行う

## カスタムルール（自由に追記してください）
```

#### 運用方針

- `OPERANT.md` はユーザーが直接編集してエージェントの挙動を制御する
- 禁止操作・応答スタイル・優先ツール・ドメイン固有のルールなどを自由に記述可能
- 変更はWebパネル再起動なしに次のタスク実行から反映（起動時にファイルを読み込む）
- Prompt Cachingのキャッシュブロック対象に含める

### 3.4 システムプロンプト構成

```
[固定部: キャッシュ対象]
 └─ エージェント役割定義・アクション仕様・出力フォーマット説明

[OPERANT.md の内容: キャッシュ対象]
 └─ ユーザー定義ルール

[動的部: 毎回更新]
 └─ 会話履歴サマリー + 直近Nターン + 今回のスクショ/テキスト + タスク指示
```

---

## 4. トークン最適化

### 4.1 画像最適化

| 施策 | 詳細 |
|------|------|
| 差分検出 | SSIM（構造的類似度）で前フレームと比較、閾値以上の類似なら送信スキップ |
| ROIクロップ | 変化があった領域のBounding Boxを検出し、パディングを加えてクロップ送信 |
| タイル分割送信 | 画面を4〜6分割し変化があったタイルのみ送信。ROIクロップより細かく制御可能 |
| リサイズ | 最大1280×720にリサイズ |
| WebP圧縮 | quality=80でWebP変換（JPEG比15〜20%削減、Pillow標準サポート） |
| グレースケール自動切替 | テキスト読み取り・UI操作座標特定など色不要なタスクは自動的にグレースケール送信（30〜40%削減）。色が重要なタスク（画像編集等）は除外 |
| スクショ履歴の分離 | 過去のスクショはコンテキストに積まず、常に最新1枚のみ送信。会話履歴はテキストのみ保持 |
| スクショのLLM制御 | エージェント側での定期送信をやめ、LLM自身が `screenshot` アクションをリクエストした時のみ取得・送信。テキストで完結できる操作後は自然にスクショ不要と判断させる。OPERANT.mdに「UIの視覚確認が必要な場合のみrequestすること」と明記 |

### 4.2 プロンプト最適化

| 施策 | 詳細 |
|------|------|
| Prompt Caching | 固定システムプロンプト + OPERANT.md をキャッシュブロックに配置 |
| キャッシュウォームアップ | Anthropic Prompt Cachingの有効期限（5分）切れを防ぐため長時間タスク時に定期的なウォームアップリクエストを送信 |
| 会話履歴の刈り込み | 直近Nターンのみ保持、古いターンは1行サマリーに圧縮 |
| 完了ステップ削除 | DONEになったステップは履歴から除去 |
| タスク種別自動判定 | タスク開始時に軽量モデルでタスク種別（ファイル操作 / UI操作 / ブラウザ等）を分類し、画像送信モードや使用モデルを自動切替 |

### 4.3 出力最適化

| 施策 | 詳細 |
|------|------|
| max_tokens制限 | デフォルト256、設定変更可 |
| 2段階LLM（オプション） | 通常操作は軽量モデル（Haiku / GPT-4o-mini）、複雑な判断のみ上位モデルへ切り替え |
| Extended Thinking 制御 | 通常操作は思考モードOFF、複雑な判断場面のみONに切り替え（Claude / o系モデル対応） |
| Assistant Prefill | Anthropic APIのassistantターン先頭に `THINK:` を埋め込み、余計な前置きなしで本題から返させる |

---

## 5. 安全設計

| 機能 | 詳細 |
|------|------|
| Webパネル認証 | パスワード認証（bcryptハッシュ化）、HTTP-only Cookieセッション管理 |
| 緊急停止ボタン | WebUI上部に常設、即時エージェントループ停止 |
| pyautogui フェイルセーフ | マウスを画面左上隅に移動すると自動停止 |
| コマンド実行タイムアウト | `cmd` アクションはデフォルト30秒でタイムアウト |
| コマンド出力サイズ上限 | stdout/stderr は上限サイズでトリミング、LLMへの過大送信を防止 |
| 操作前確認モード | config で有効化すると各ACTの実行前にWebUI上で確認を求める（オプション） |
| ローカル限定アクセス | WebパネルはLAN内のみバインド |
| OPERANT.md 禁止操作 | システムファイル・レジストリ書き込み等をデフォルトで禁止定義 |
| web_fetch 制限 | オプション機能。有効時もHTMLをMarkdown変換・上限文字数トリミングしてからLLMへ渡す（トークン爆発防止）。アクセス可能URLのホワイトリスト設定も可 |

---

## 6. 技術スタック

### バックエンド（Python）

| ライブラリ | 用途 |
|-----------|------|
| FastAPI | HTTP + WebSocket サーバー |
| mss | 高速スクリーンショット取得 |
| pyautogui | マウス・キーボード操作 |
| Pillow | 画像リサイズ・WebP変換 |
| scikit-image | SSIM差分検出 |
| pywinauto | Accessibility API経由UIテキスト取得 |
| psutil | プロセス・システム情報取得 |
| pyperclip | クリップボード操作 |
| aiofiles | 非同期ファイルI/O |
| bcrypt | パスワードハッシュ化 |
| anthropic | Claude API SDK |
| openai | OpenAI / Azure OpenAI SDK |
| google-genai | Gemini SDK |
| PyYAML | 設定ファイル読み込み |

### フロントエンド

- 素のHTML / CSS / JavaScript（フレームワークなし、CDN不要）
- WebSocket でリアルタイム通信
- Canvas API でスクショプレビュー表示

---

## 7. プロジェクト構成

```
operant/
├── agent/
│   ├── core.py          # メインエージェントループ
│   ├── screenshot.py    # スクショ取得・差分検出・WebP変換
│   ├── controller.py    # マウス・キーボード操作
│   ├── tools.py         # テキスト直接処理ツール群（cmd・ファイル等）
│   └── context.py       # 会話履歴管理・要約・刈り込み
├── llm/
│   ├── base.py          # 抽象基底クラス・システムプロンプト
│   ├── claude.py        # Anthropic Claude
│   ├── openai.py        # OpenAI / Azure OpenAI
│   └── gemini.py        # Google Gemini
├── web/
│   ├── server.py        # FastAPI + WebSocket + 認証
│   └── static/
│       ├── index.html
│       ├── login.html
│       ├── app.js
│       └── style.css
├── i18n/
│   ├── ja.yaml          # 日本語リソース
│   └── en.yaml          # 英語リソース
├── setup.py             # CLIセットアップウィザード
├── OPERANT.md           # LLMルール定義（セットアップ時自動生成・ユーザー編集可）
├── config.yaml          # 設定ファイル（セットアップ時自動生成）
├── main.py              # 起動エントリーポイント
├── requirements.txt
└── README.md
```

---

## 8. 設定ファイル（config.yaml）

セットアップウィザードで自動生成される。手動編集も可能。

```yaml
# 言語設定
language: ja              # BCP 47 言語コード（ja / en）

# 使用LLM
llm:
  provider: claude          # claude / openai / azure_openai / gemini
  model: claude-opus-4-6
  max_tokens: 256
  # two_stage:
  #   light_model: claude-haiku-4-5-20251001
  #   heavy_model: claude-opus-4-6
  #   threshold: 0.7

# APIキー（環境変数推奨）
api_keys:
  anthropic: ${ANTHROPIC_API_KEY}
  openai:    ${OPENAI_API_KEY}
  gemini:    ${GEMINI_API_KEY}

# スクリーンショット設定
screenshot:
  max_width: 1280
  max_height: 720
  quality: 80
  format: webp
  diff_threshold: 0.97
  capture_delay_ms: 500

# エージェント設定
agent:
  loop_timeout: 300
  cmd_timeout: 30
  cmd_max_output: 8000
  confirm_before_act: false
  web_fetch_enabled: false      # Webドキュメント取得（外部通信を伴うためデフォルト無効）
  web_fetch_max_chars: 12000    # 取得コンテンツの上限文字数
  # web_fetch_allowlist:        # アクセス可能URLホワイトリスト（省略時は全URL許可）
  #   - "https://docs.python.org"
  #   - "https://stackoverflow.com"

# Webパネル設定
web:
  host: 0.0.0.0
  port: 8765
  session_expire_hours: 24
  password_hash: "$2b$12$..."  # bcryptハッシュ（セットアップ時に自動設定）
  context_history: 10
```

---

## 9. 非機能要件

| 項目 | 要件 |
|------|------|
| 対応OS | Windows 10 / 11 |
| Python バージョン | 3.11 以上 |
| ライセンス | MIT |
| 外部通信 | LLM API呼び出しのみ |
| ネットワーク | LAN内のみ（外部公開非対応） |
| ログ | 実行ログをローカルファイルに保存 |
| 対応言語（初期） | 日本語・英語 |

---

## 10. 今後の検討事項（スコープ外）

- macOS / Linux 対応
- 対応言語の追加（中国語・韓国語等）
- AVIF画像フォーマット対応（LLM APIが正式サポートしたタイミングで追加）
- ブラウザ拡張機能との連携（DOM直接取得）
- タスクのスケジューリング・自動実行
- ローカルLLM（Ollama等）対応
- Webパネルでの OPERANT.md 編集UI
