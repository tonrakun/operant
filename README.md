# Operant

> LLMがスクリーンショットを見ながら Windows を自律操作するローカルエージェント

**バージョン:** 1.0.0 | **ライセンス:** MIT | **対応OS:** Windows 10 / 11

---

## 目次

1. [概要](#概要)
2. [デモ・動作イメージ](#デモ動作イメージ)
3. [機能一覧](#機能一覧)
4. [動作要件](#動作要件)
5. [インストール](#インストール)
6. [セットアップ（初回起動）](#セットアップ初回起動)
7. [起動・使い方](#起動使い方)
8. [設定ファイル（config.yaml）](#設定ファイルconfigyaml)
9. [エージェントルール定義（OPERANT.md）](#エージェントルール定義operantmd)
10. [LLMプロバイダー](#llmプロバイダー)
11. [対応アクション一覧](#対応アクション一覧)
12. [プロジェクト構成](#プロジェクト構成)
13. [セキュリティについて](#セキュリティについて)
14. [トラブルシューティング](#トラブルシューティング)
15. [今後の予定](#今後の予定)

---

## 概要

**Operant** は、チャット形式の指示を送るだけで LLM が Windows PC を自律操作してくれるローカルエージェントです。

ブラウザ上の Web パネルからテキストで指示を出すと、エージェントがスクリーンショットを確認しながらマウス・キーボード操作、ファイル操作、コマンド実行など必要な作業をすべて自動で行います。

### 設計方針

| 方針 | 詳細 |
|------|------|
| **ローカル完結** | LLM API 呼び出し以外の外部通信は一切なし |
| **LAN 限定アクセス** | Web パネルはローカルネットワーク内のみ（外部公開非対応） |
| **プライバシー優先** | 学習利用なしの API（Anthropic Claude）を第一推奨。Ollama 使用時は完全ローカル |
| **シンプルな依存関係** | 標準的な Python ライブラリのみ、フロントエンドは素の HTML/JS |
| **Windows 専用** | 現バージョンは Windows 10/11 のみ対応 |
| **多言語対応** | 日本語・英語・中国語（簡体）・韓国語に対応（OS ロケールを自動検出） |

---

## デモ・動作イメージ

```
ユーザー（Web パネル）: 「デスクトップにある report.txt を開いて、先頭に今日の日付を追記して」

エージェント:
  THINK: ファイルを直接読み込んで内容を確認し、先頭に日付を追記する。
  ACT: {"action": "file_read", "path": "C:/Users/.../Desktop/report.txt"}

  THINK: ファイルの内容を取得した。先頭に日付を追記して書き込む。
  ACT: {"action": "file_write", "path": "C:/Users/.../Desktop/report.txt",
        "content": "2026-03-17\n<元の内容>", "mode": "overwrite"}

  DONE: report.txt の先頭に本日の日付を追記しました。
```

質問への回答例：

```
ユーザー: 「今何時ですか？」

エージェント:
  REPLY: 現在の時刻はシステムにアクセスできないため、タスクバーや時計アプリでご確認ください。
```

### Web パネルのレイアウト

```
┌──────────────────────────────────────────────────────────────────────────┐
│  Operant  [実行中]  [Step 3]       ●  [⚙] [✏] [⏹] [⏻]                 │
├─────────────────────────┬────────────────────────────────────────────────┤
│  LIVE スクショビュー    │  チャット              [💾][📂][🗑]            │
│                         │  ─────────────────────────────────────────── │
│  [最新スクリーン        │  Cost $0.000450  ↑1200 ↓80                   │
│   ショット表示]         │  ─────────────────────────────────────────── │
│                         │  あなた: Chrome を開いて GitHub にアクセスして│
│  動作中: LIVE バッジ    │                                                │
│                         │  思考: Chrome を起動する...       [コピー]    │
│  [時刻] [↓]            │  ▶ ACT: {"action": "cmd", ...}   12:34:55     │
│  クリックで拡大         │  ● 生成中...  ●  ●                            │
│                         │  ─────────────────────────────────────────── │
│                         │  [タスクを入力...]                       [➤]  │
└─────────────────────────┴────────────────────────────────────────────────┘
```

---

## 機能一覧

### PC 自律操作

| 機能 | 内容 |
|------|------|
| マウス操作 | クリック・ダブルクリック・右クリック・ドラッグ・スクロール |
| キーボード操作 | テキスト入力・キー押下・ショートカット |
| スクリーンショット | mss による高速キャプチャ、差分検出付き、WebP 圧縮 |

### テキスト直接処理ツール（スクショ不要・高効率）

| ツール | 内容 |
|--------|------|
| `file_read` | テキストファイルを直接読み込んで LLM へ渡す（offset/limit 対応） |
| `file_write` | ファイルへの書き込み・上書き・追記（親ディレクトリ自動作成） |
| `file_delete` | ファイル・ディレクトリの削除 |
| `file_copy` | ファイル・ディレクトリのコピー |
| `file_move` | ファイル・ディレクトリの移動・リネーム |
| `file_search` | glob パターンによるファイル検索（再帰対応） |
| `find_in_file` | ファイル内テキスト検索（行番号付き） |
| `dir_list` | ディレクトリ一覧取得（ファイルサイズ付き） |
| `cmd` | コマンドプロンプト / PowerShell の実行 |
| `clipboard_read` | クリップボード内容の取得 |
| `clipboard_write` | クリップボードへのテキスト書き込み |
| `get_windows` | 開いているウィンドウ一覧取得（表示状態付き） |
| `window_focus` | 指定ウィンドウを前面に表示・フォーカス |
| `get_processes` | 実行中プロセス一覧取得（メモリ使用量付き） |
| `process_kill` | プロセスの強制終了（PID または名前で指定） |
| `app_launch` | アプリケーションの起動 |
| `get_ui_text` | Windows Accessibility API 経由で UI 要素テキスト取得 |
| `get_env` | 環境変数の取得 |
| `get_sysinfo` | CPU・メモリ・ディスク使用率等の取得 |
| `web_fetch` | URL の HTML を Markdown 変換して取得（オプション） |

### Web パネル

- チャット形式のインターフェース（リアルタイム WebSocket 通信）
- 左ペイン: LIVE スクリーンショットビュー（クリックで拡大、WebP ダウンロード）
- 右ペイン: エージェントとのチャット
- **アイコンボタン UI** — ヘッダー・チャットのボタンを SVG アイコン化。ホバーでツールチップ表示
- **リアルタイム APIコスト表示** — チャットルームごとの累積コスト・トークン数をリアルタイム表示
- **config.yaml 設定 UI** — ⚙ ボタンからブラウザ上で設定を編集・保存
- **OPERANT.md 編集 UI** — ✏ ボタンからエージェントルールを直接編集
- 緊急停止ボタン（⏹、即時エージェントループ停止）
- **ループ検出** — 同一アクションが 3 回連続した場合に自動停止
- **LLM 生成中インジケーター**（「生成中...」アニメーション）
- **アクションログ表示**（実行中のアクションをチャット上に薄いログとして表示）
- **ステップカウンター**（現在タスクの思考ターン数をヘッダーで確認）
- **メッセージタイムスタンプ・コピーボタン**
- パスワード認証（bcrypt ハッシュ化）
- 保存チャット機能（YAML で保存・ロード）

---

## 動作要件

| 項目 | 要件 |
|------|------|
| OS | Windows 10 / 11 |
| Python | 3.11 以上 |
| インターネット接続 | LLM API 呼び出しに必要 |
| LLM API キー | Anthropic / OpenAI / Azure OpenAI / Google Gemini のいずれか |

---

## インストール

### 方法 1: install.bat（推奨）

1. リポジトリをダウンロード（ZIP または `git clone`）
2. フォルダ内の **`install.bat`** をダブルクリック

```
install.bat が自動で行うこと:
  - Python 3.11 以上の確認（なければダウンロードページへ誘導）
  - 仮想環境（.venv）の作成
  - 依存パッケージのインストール
  - セットアップウィザードの起動
```

> **Python が未インストールの場合:** https://www.python.org/downloads/ からインストールし、
> 「Add Python to PATH」にチェックを入れてください。

### 方法 2: 手動インストール

```bash
git clone https://github.com/tonrakun/operant.git
cd operant
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

> **注意:** `pywinauto` など一部ライブラリは Windows 専用です。

---

## セットアップ（初回起動）

初回は対話形式のウィザードで設定を行います。

```bash
python main.py
```

`config.yaml` が存在しない場合、自動的にセットアップウィザードが起動します。

### セットアップの流れ

```
Welcome to Operant Setup!
言語を選択してください / Select language:
  [1] 日本語
  [2] English
  > 1

[1/5] LLMプロバイダーを選択してください:
  [1] Anthropic Claude（推奨: 学習利用なし）
  [2] OpenAI GPT-4o
  [3] Azure OpenAI
  [4] Google Gemini
  > 1

[2/5] APIキーを入力してください:
  > （入力は非表示）

[3/5] 接続テストを実行します... ✓ OK

[4/5] Webパネルのパスワードを設定してください:
  パスワード     > （8文字以上）
  パスワード確認 > （再入力）

[5/5] セットアップ完了！
  設定ファイル: config.yaml
  LLMルール定義: OPERANT.md（編集でエージェントの挙動をカスタマイズ可能）
  起動: python main.py
```

セットアップ完了後、以下のファイルが生成されます：

| ファイル | 内容 |
|---------|------|
| `config.yaml` | LLM・Web パネル等の設定 |
| `OPERANT.md` | エージェントのルール定義（自由に編集可能） |
| `logs/` | 実行ログの保存ディレクトリ |

### セットアップのやり直し

```bash
python main.py --setup
# または
start.bat  # config.yaml がなければ自動でウィザードを起動
```

---

## 起動・使い方

### 起動

**`start.bat`** をダブルクリックするだけで起動します。起動後は自動でブラウザが開きます。

```bash
# コマンドラインから起動する場合
python main.py
```

ブラウザが自動で開かない場合は手動でアクセスしてください（同一 PC から）：

```
http://localhost:8765
```

LAN 内の別デバイス（スマホ・タブレット等）からもアクセス可能：

```
http://<PC の IP アドレス>:8765
```

### 使い方

1. ログインページでセットアップ時に設定したパスワードを入力
2. チャット欄に指示を日本語（または英語）で入力して送信（`Ctrl+Enter` でも送信可）
3. エージェントが作業を開始し、思考・操作ログ・完了通知がリアルタイムで表示される
4. 作業を中断したい場合は **⏹ ボタン（緊急停止）** をクリック

### ヘッダーボタン

| ボタン | 機能 |
|--------|------|
| ⚙ | config.yaml の設定を Web UI から編集 |
| ✏ | OPERANT.md（エージェントルール）をブラウザ上で編集 |
| ⏹ | エージェントを即時停止（緊急停止） |
| ⏻ | ログアウト |

### 指示の例

```
# ファイル操作
「デスクトップの data.csv を開いて内容を教えて」
「C:/projects/README.md に今日の変更履歴を追記して」
「logs フォルダ内の *.log ファイルを全部検索して」

# アプリ操作
「メモ帳を開いてサンプルのPythonコードを書いて保存して」
「Chromeで github.com を開いて」

# システム操作
「現在起動中のプロセス一覧を教えて」
「CPU とメモリの使用率を確認して」
「notepad.exe を終了させて」

# 質問（ツールなしで即回答）
「Pythonのリスト内包表記の書き方を教えて」
「このエラーメッセージはどういう意味？」
```

### pyautogui フェイルセーフ

**マウスカーソルを画面の左上隅（0, 0）に素早く移動**すると、エージェントの操作が即時停止します。

---

## 設定ファイル（config.yaml）

セットアップウィザードで自動生成されます。**Web パネルの ⚙ ボタンからも編集可能**です（APIキー・パスワード以外）。

```yaml
# 言語設定（ja / en / zh / ko）
language: ja

# LLM設定
llm:
  provider: claude          # claude / openai / azure_openai / gemini / ollama
  model: claude-sonnet-4-6  # 使用するモデル名

# APIキー（環境変数参照または直接記載）
api_keys:
  anthropic: ${ANTHROPIC_API_KEY}   # 環境変数参照の場合
  openai:    ${OPENAI_API_KEY}
  gemini:    ${GEMINI_API_KEY}

# スクリーンショット設定
screenshot:
  max_width: 1280           # リサイズ後の最大幅（px）
  max_height: 720           # リサイズ後の最大高さ（px）
  quality: 80               # WebP 圧縮品質（0-100）
  format: webp              # 画像フォーマット
  diff_threshold: 0.97      # 差分検出の閾値（SSIM）
  capture_delay_ms: 500     # 操作後のスクショ取得待機時間（ms）

# エージェント設定
agent:
  loop_timeout: 300              # タスク全体のタイムアウト（秒）
  cmd_timeout: 30                # コマンド実行のタイムアウト（秒）
  cmd_max_output: 8000           # コマンド出力の最大文字数
  confirm_before_act: false      # true にすると各操作前に確認ダイアログを表示
  web_fetch_enabled: false       # Web ドキュメント取得機能（外部通信が発生）
  web_fetch_max_chars: 12000     # 取得コンテンツの上限文字数

# Webパネル設定
web:
  host: 0.0.0.0             # バインドアドレス
  port: 8765                # ポート番号
  session_expire_hours: 24  # セッション有効期限（時間）
  password_hash: "$2b$12$..." # bcrypt ハッシュ（セットアップ時に自動設定）
  context_history: 10       # 会話履歴として保持するターン数
```

### APIキーの環境変数設定（推奨）

**PowerShell（現在のセッションのみ）:**
```powershell
$env:ANTHROPIC_API_KEY = "sk-ant-..."
python main.py
```

**システム環境変数として永続化（推奨）:**
1. `スタート` → `システム環境変数の編集` → `環境変数`
2. ユーザー環境変数に `ANTHROPIC_API_KEY` を追加

---

## エージェントルール定義（OPERANT.md）

セットアップ時に自動生成される `OPERANT.md` を編集することで、エージェントの挙動をカスタマイズできます。

このファイルはシステムプロンプトの末尾に自動で追記されます。**Web パネルの再起動なしに**、次のタスク実行から変更が反映されます。

### デフォルト内容（日本語の場合）

```markdown
# Operant Rules

## 基本ルール
- 必ずTHINK:またはREPLY:で始め、1〜2文で状況・意図を簡潔に述べる
- 操作が必要なときのみACT:を添える
- タスク完了時はDONE:で締める
- 余計な説明・謝罪・前置きは不要

## ツール選択優先順位
1. テキスト直接取得ツール（file_read, cmd, get_windows等）で完結できるか確認
2. 無理なら Accessibility API（get_ui_text）でUI要素テキスト取得を試みる
3. それも無理ならスクショ（screenshot）経由にフォールバック

## 禁止操作
- システムファイル（C:\Windows 以下）の書き込み・削除
- レジストリの書き込み
- ネットワーク設定の変更

## 応答言語
- ユーザーへの返答は日本語で行う
```

---

## LLMプロバイダー

| プロバイダー | モデル例 | 学習利用 | 備考 |
|------------|---------|---------|------|
| **Anthropic Claude** | claude-sonnet-4-6 | デフォルト対象外 | **第一推奨** |
| OpenAI GPT-4o | gpt-4o | opt-out 設定推奨 | 第二推奨 |
| Azure OpenAI | gpt-4o | エンタープライズ契約で保護 | 企業向け推奨 |
| Google Gemini | gemini-2.0-flash | DPA 締結で保護 | 第三推奨 |
| **Ollama（ローカル）** | llava, llava-llama3 等 | なし（完全ローカル） | **プライバシー最優先** |

すべてのプロバイダーで **Vision（画像入力）** が必須です（Ollama は Vision 対応モデルを選択）。

### Ollama のセットアップ

1. [Ollama](https://ollama.com/) をインストール
2. Vision 対応モデルを pull：
   ```bash
   ollama pull llava
   ```
3. セットアップウィザードでプロバイダー `[5] Ollama` を選択
4. サーバーアドレス（デフォルト: `http://localhost:11434`）とモデル名を入力

`config.yaml` での手動設定：

```yaml
llm:
  provider: ollama
  model: llava
  ollama_base_url: http://localhost:11434
```

### Azure OpenAI の追加設定

```yaml
llm:
  provider: azure_openai
  model: gpt-4o
  azure_endpoint: https://YOUR_RESOURCE.openai.azure.com/
  azure_deployment: gpt-4o
```

---

## 対応アクション一覧

### マウス・キーボード操作

```jsonc
{"action": "click",        "x": 320, "y": 450}
{"action": "double_click", "x": 320, "y": 450}
{"action": "right_click",  "x": 320, "y": 450}
{"action": "drag",         "x1": 100, "y1": 100, "x2": 400, "y2": 400}
{"action": "scroll",       "x": 500, "y": 300, "dir": "down", "amount": 3}
{"action": "type",         "text": "入力テキスト"}
{"action": "key",          "key": "enter"}  // ctrl+c, alt+f4 等も可
```

### ファイル操作

```jsonc
{"action": "file_read",   "path": "C:/foo.txt"}
{"action": "file_read",   "path": "C:/foo.txt", "offset": 0, "limit": 50}  // 行範囲指定
{"action": "file_write",  "path": "C:/foo.txt", "content": "...", "mode": "overwrite"}
// mode: "overwrite"（上書き）/ "append"（追記）
{"action": "file_delete", "path": "C:/foo.txt"}
{"action": "file_copy",   "src": "C:/src.txt", "dst": "C:/dst.txt"}
{"action": "file_move",   "src": "C:/old.txt", "dst": "C:/new.txt"}
{"action": "dir_list",    "path": "C:/project"}
{"action": "file_search", "path": "C:/Users", "pattern": "*.pdf", "recursive": true}
{"action": "find_in_file","path": "C:/code.py", "query": "def main"}
```

### コマンド・システム

```jsonc
{"action": "cmd",             "command": "dir C:\\Users", "timeout": 30}
{"action": "clipboard_read"}
{"action": "clipboard_write", "text": "..."}
{"action": "get_windows"}
{"action": "window_focus",    "title": "Notepad"}
{"action": "get_processes"}
{"action": "process_kill",    "pid": 1234}
{"action": "process_kill",    "name": "notepad.exe"}
{"action": "app_launch",      "path": "notepad.exe", "args": []}
{"action": "get_ui_text",     "window": "Notepad"}
{"action": "get_env",         "key": "PATH"}
{"action": "get_sysinfo"}
```

### スクリーンショット・Web

```jsonc
// 視覚確認が必要なときのみ使用
{"action": "screenshot"}

// web_fetch_enabled: true の場合のみ使用可能
{"action": "web_fetch", "url": "https://docs.python.org"}
```

### 制御

```jsonc
{"action": "wait", "reason": "ロード待ち", "ms": 1000}
{"action": "done", "summary": "完了した内容を1行で"}
```

---

## LLM 出力フォーマット

エージェントは以下の 4 パターンのみで応答します：

| パターン | 使用場面 | 形式 |
|----------|---------|------|
| **Pattern 1** | 質問への回答・会話 | `REPLY: <ユーザーへの返答>` |
| **Pattern 2** | ツール実行（返答なし） | `THINK: <理由>`<br>`ACT: {"action": ...}` |
| **Pattern 3** | 返答しながらツール実行 | `REPLY: <簡単な説明>`<br>`ACT: {"action": ...}` |
| **Pattern 4** | タスク完了 | `DONE: <完了サマリー>` |

- `REPLY:` はユーザー向けテキスト（青色で表示）
- `THINK:` はエージェント内部推論（薄いグレーで表示）
- `ACT:` はツール呼び出し JSON（ログとして表示）
- 同一アクションが **3 回連続** すると自動停止（ループ検出）

---

## プロジェクト構成

```
operant/
├── agent/
│   ├── core.py          # メインエージェントループ（LLM呼び出し・パース・アクション実行・ループ検出）
│   ├── screenshot.py    # スクショ取得・差分検出（SSIM）・WebP変換
│   ├── controller.py    # マウス・キーボード操作（pyautogui）
│   ├── tools.py         # テキスト直接処理ツール群（ファイル・プロセス・クリップボード等）
│   ├── context.py       # 会話履歴管理・要約・刈り込み
│   └── __init__.py
├── llm/
│   ├── base.py          # 抽象基底クラス・システムプロンプト（REPLY/THINK/ACT/DONE形式）・ファクトリ
│   ├── claude.py        # Anthropic Claude 実装（トークン使用量追跡）
│   ├── openai.py        # OpenAI / Azure OpenAI 実装（トークン使用量追跡）
│   ├── gemini.py        # Google Gemini 実装
│   ├── ollama.py        # Ollama ローカル LLM 実装
│   └── __init__.py
├── web/
│   ├── server.py        # FastAPI + WebSocket + 認証 + config API
│   ├── static/
│   │   ├── index.html   # メインチャット画面（SVG アイコンボタン）
│   │   ├── login.html   # ログイン画面
│   │   ├── app.js       # フロントエンド JS（WebSocket・コスト表示・設定UI）
│   │   └── style.css    # スタイル
│   └── __init__.py
├── i18n/
│   ├── ja.yaml          # 日本語リソース
│   ├── en.yaml          # 英語リソース
│   ├── zh.yaml          # 中国語（簡体）リソース
│   └── ko.yaml          # 韓国語リソース
├── logs/                # 実行ログ（自動作成）
├── install.bat          # ワンクリックインストーラー（Python確認・venv・pip install・セットアップ）
├── start.bat            # ワンクリック起動スクリプト
├── main.py              # エントリーポイント
├── setup.py             # CLIセットアップウィザード
├── requirements.txt     # 依存パッケージ
├── config.yaml          # 設定ファイル（セットアップ時に自動生成）
└── OPERANT.md           # LLMルール定義（セットアップ時に自動生成・ユーザー編集可）
```

---

## セキュリティについて

| 機能 | 詳細 |
|------|------|
| **パスワード認証** | bcrypt ハッシュ化、HTTP-only Cookie によるセッション管理 |
| **LAN 限定** | Web パネルは `0.0.0.0` バインドだが外部公開は非推奨 |
| **緊急停止** | Web パネル上部の ⏹ ボタンで即時ループ停止 |
| **ループ検出** | 同一アクションが 3 回連続した場合に自動停止 |
| **pyautogui フェイルセーフ** | マウスを画面左上（0,0）に移動すると自動停止 |
| **コマンドタイムアウト** | `cmd` アクションはデフォルト 30 秒でタイムアウト |
| **出力サイズ上限** | コマンド出力は上限文字数でトリミング |
| **config API 保護** | Web UI からの設定変更は安全なキーのみ許可（APIキー・パスワード除外） |
| **web_fetch 制限** | オプション機能。HTML を Markdown 変換・上限文字数トリミング後に渡す |

### 外部公開について

Operant は**外部公開を想定していません**。ngrok などで公開することは非推奨です。LAN 内のみでご利用ください。

---

## トラブルシューティング

### インストール・起動時のエラー

---

#### `pip install` 中に `ERROR: Microsoft Visual C++ 14.0 or greater is required`

**原因:** `pywinauto` などのコンパイルが必要なパッケージのビルドに Visual C++ が必要です。

**解決策:**

1. [Microsoft C++ Build Tools](https://visualstudio.microsoft.com/visual-cpp-build-tools/) をインストール
2. インストール時に「C++ によるデスクトップ開発」を選択
3. インストール後にターミナルを再起動してから `pip install` を再実行

---

#### `ModuleNotFoundError: No module named 'xxx'`

```bash
.venv\Scripts\activate
pip install -r requirements.txt
```

---

#### `config.yaml not found. Starting setup wizard...` が毎回表示される

```bash
python main.py --setup
```

---

### LLM API のエラー

---

#### `LLM error: AuthenticationError` / `Invalid API Key`

1. 各プロバイダーのダッシュボードで API キーを確認
2. `python main.py --setup` で API キーを再設定
3. 環境変数を使用している場合：
   ```powershell
   echo $env:ANTHROPIC_API_KEY
   ```

---

#### `LLM error: RateLimitError`

1. しばらく待ってから再試行
2. API プランのアップグレードを検討

---

#### `Task timeout (300s)`

```yaml
agent:
  loop_timeout: 600   # 10分に延長
```

---

#### `Loop detected: same action repeated 3 times`

エージェントが同じ操作を繰り返していることを検出して自動停止しました。

**解決策:**

1. タスクを再送して別のアプローチを試みさせる
2. OPERANT.md に「同じアクションが失敗したら別の方法を試すこと」と追記

---

### スクリーンショット・操作のエラー

---

#### `pyautogui.FailSafeException: PyAutoGUI fail-safe triggered`

マウスカーソルが画面左上（0, 0）に移動したため、フェイルセーフが発動しました。正常な安全機能です。再度タスクを指示して再開してください。

---

#### スクリーンショットが真っ黒になる

1. 管理者権限でターミナルを起動して `python main.py` を実行
2. 対象のアプリが最小化されていないか確認

---

#### クリック座標がずれる

```yaml
screenshot:
  max_width: 1920
  max_height: 1080
```

Windows の表示スケーリングを 100% に設定することも有効です。

---

### Web パネルのエラー

---

#### ブラウザで `http://localhost:8765` に接続できない

```yaml
web:
  port: 8766   # 別のポートを試す
```

```powershell
# ファイアウォール許可（管理者権限）
netsh advfirewall firewall add rule name="Operant" dir=in action=allow protocol=TCP localport=8765
```

---

#### パスワードを忘れた

```bash
python main.py --setup
```

---

### ログの確認方法

```
logs/operant.log
```

---

## 変更履歴

### v1.0.0（latest）

- **ワンクリックインストーラー** — `install.bat` を追加。Python バージョン確認・仮想環境作成・pip install・セットアップウィザード起動をすべて自動化。Visual C++ Build Tools 不足時も案内メッセージを表示
- **ワンクリック起動スクリプト** — `start.bat` を追加。仮想環境の有効化・サーバー起動を自動化。`config.yaml` が未作成の場合はセットアップウィザードへ誘導
- **ブラウザ自動オープン** — サーバー起動後に自動でブラウザを開くように変更

### v0.4.0

- **LLM 出力フォーマット再設計** — `REPLY:` タグを追加し、テキスト回答とツール呼び出しを明確に分離。質問には即 `REPLY:` で回答し、ツールが必要な場合のみ `ACT:` を出力。`THINK:` は内部推論専用に
- **ループ検出** — 同一アクションが 3 回連続した場合に自動停止。無限ループを防止
- **ツールの大幅拡充** — `file_delete`、`file_copy`、`file_move`、`file_search`（glob パターン検索）、`find_in_file`（行番号付き文字列検索）、`process_kill`、`app_launch`、`window_focus` を新規追加
- **既存ツール強化** — `dir_list` にファイルサイズ表示、`get_processes` にメモリ使用量表示、`get_windows` に表示状態表示、`file_read` に行範囲指定（offset/limit）を追加
- **アイコンボタン UI** — ヘッダー・チャットのすべてのボタンを SVG アイコンに変更。視覚的にコンパクトで分かりやすい UI に
- **config.yaml 設定 UI** — ⚙ ボタンから Web パネル上で設定を編集・保存できる設定画面を追加
- **API コスト表示** — チャットルームごとの累積コスト・トークン数をリアルタイムで表示。履歴クリアでリセット
- **出力トークン制限廃止** — `max_tokens` の制限を廃止し、システムプロンプトによる簡潔な回答指示に変更

### v0.3.0（2026-03-17）

- **Ollama（ローカル LLM）対応** — `provider: ollama` 設定で Ollama を使用可能
- **OPERANT.md 編集 UI** — Web パネルのヘッダーにルール編集ボタンを追加
- **多言語対応の拡充** — 中国語（簡体）・韓国語を追加

---

## ライセンス

MIT License

---

## 貢献・フィードバック

バグ報告・機能要望は Issue でお気軽にどうぞ。
Pull Request も歓迎します。
