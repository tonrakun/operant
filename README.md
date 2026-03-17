# Operant

> LLMがスクリーンショットを見ながら Windows を自律操作するローカルエージェント

**バージョン:** 0.4.0 | **ライセンス:** MIT | **対応OS:** Windows 10 / 11

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

### Web パネルのレイアウト

```
┌──────────────────────────────────────────────────────────────────────────┐
│  Operant  [実行中]  [Step 3]          ● [ルール編集] [緊急停止] [ログアウト] │
├─────────────────────────┬────────────────────────────────────────────────┤
│  LIVE スクショビュー    │  チャット                                      │
│                         │                                                │
│  [最新スクリーン        │  あなた: Chrome を開いて GitHub にアクセスして │
│   ショット表示]         │                                                │
│                         │  思考: Chrome を起動する...        [コピー]    │
│  動作中: LIVE バッジ    │  ▶ ACT: {"action": "cmd", ...}   12:34:55     │
│                         │  ● 生成中...  ●  ●                             │
│  [時刻] [↓ダウンロード]│                                                │
│  クリックで拡大         │  ──────────────────────────────────────────── │
│                         │  [タスクを入力...]                    [送信]   │
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
| `file_read` | テキストファイルを直接読み込んで LLM へ渡す |
| `file_write` | ファイルへの書き込み・上書き・追記 |
| `dir_list` | ディレクトリ一覧取得 |
| `cmd` | コマンドプロンプト / PowerShell の実行 |
| `clipboard_read` | クリップボード内容の取得 |
| `clipboard_write` | クリップボードへのテキスト書き込み |
| `get_windows` | 開いているウィンドウ一覧取得 |
| `get_processes` | 実行中プロセス一覧取得 |
| `get_ui_text` | Windows Accessibility API 経由でUI要素テキスト取得 |
| `get_env` | 環境変数の取得 |
| `get_sysinfo` | CPU・メモリ・ディスク使用率等の取得 |
| `web_fetch` | URL の HTML を Markdown 変換して取得（オプション） |

### Web パネル

- チャット形式のインターフェース（リアルタイム WebSocket 通信）
- 左ペイン: LIVE スクリーンショットビュー
- 右ペイン: エージェントとのチャット
- 緊急停止ボタン（即時エージェントループ停止）
- **OPERANT.md 編集 UI**（ヘッダーの「ルール編集」ボタンからブラウザ上で直接編集可能）
- **LLM 生成中インジケーター**（「生成中...」アニメーションでエージェントの動作を視覚的に確認）
- **アクションログ表示**（実行中のアクションをチャット上に薄いログとして表示）
- **ステップカウンター**（現在タスクの思考ターン数をヘッダーで確認）
- **メッセージタイムスタンプ**（各メッセージの受信時刻をホバー時に表示）
- **コピーボタン**（メッセージ内容をワンクリックでクリップボードへ）
- **スクリーンショットダウンロード**（最新スクリーンショットを WebP ファイルとして保存）
- **WebSocket 接続状態インジケーター**（ヘッダーのドットで接続状態を常時表示）
- パスワード認証（bcrypt ハッシュ化）

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

### 1. リポジトリのクローン

```bash
git clone https://github.com/yourname/operant.git
cd operant
```

### 2. 仮想環境の作成（推奨）

```bash
python -m venv .venv
.venv\Scripts\activate
```

### 3. 依存パッケージのインストール

```bash
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

パスワード変更や LLM プロバイダーの変更など、再セットアップしたい場合：

```bash
python main.py --setup
```

---

## 起動・使い方

### 起動

```bash
python main.py
```

起動後、ブラウザで以下にアクセスします（同一 PC から）：

```
http://localhost:8765
```

LAN 内の別デバイス（スマホ・タブレット等）からもアクセス可能：

```
http://<PC の IP アドレス>:8765
```

> PC の IP アドレスは `ipconfig` コマンドで確認できます。

### 使い方

1. ログインページでセットアップ時に設定したパスワードを入力
2. チャット欄に指示を日本語（または英語）で入力して送信
3. エージェントが作業を開始し、思考（THINK）・操作ログ・完了通知（DONE）がリアルタイムで表示される
4. 作業を中断したい場合は **緊急停止ボタン** をクリック

### 指示の例

```
# ファイル操作
「デスクトップの data.csv を開いて内容を教えて」
「C:/projects/README.md に今日の変更履歴を追記して」

# アプリ操作
「メモ帳を開いてサンプルのPythonコードを書いて保存して」
「Chromeで github.com を開いて」

# システム操作
「現在起動中のプロセス一覧を教えて」
「CPU とメモリの使用率を確認して」
「デスクトップ上のファイル一覧を見せて」
```

### pyautogui フェイルセーフ

**マウスカーソルを画面の左上隅（0, 0）に素早く移動**すると、エージェントの操作が即時停止します。エージェントが想定外の操作をした場合の緊急手段として覚えておいてください。

---

## 設定ファイル（config.yaml）

セットアップウィザードで自動生成されます。手動での編集も可能です。

```yaml
# 言語設定（ja / en / zh / ko）
language: ja

# LLM設定
llm:
  provider: claude          # claude / openai / azure_openai / gemini
  model: claude-sonnet-4-6    # 使用するモデル名
  max_tokens: 256           # 1ターンあたりの最大出力トークン数

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
  diff_threshold: 0.97      # 差分検出の閾値（SSIM）。高いほど差分を検出しやすい
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
  host: 0.0.0.0             # バインドアドレス（0.0.0.0 = LAN 内全体に公開）
  port: 8765                # ポート番号
  session_expire_hours: 24  # セッション有効期限（時間）
  password_hash: "$2b$12$..." # bcrypt ハッシュ（セットアップ時に自動設定）
  context_history: 10       # 会話履歴として保持するターン数
```

### APIキーの環境変数設定（推奨）

APIキーを `config.yaml` に直接書かず、環境変数で管理する方法：

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
- システムファイル（C:\Windows 以下）の書き込み・削除
- レジストリの書き込み
- ネットワーク設定の変更

## 応答言語
- ユーザーへの返答は日本語で行う

## カスタムルール（自由に追記してください）
```

### カスタマイズ例

```markdown
## カスタムルール
- 作業前に必ず「〇〇を行います。よろしいですか？」と確認を取ること
- ファイルを削除する前に必ずバックアップを作成すること
- 作業ディレクトリは C:/projects/ 以下のみ使用すること
- コードを書く場合は Python を優先すること
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
  max_tokens: 256
  ollama_base_url: http://localhost:11434
```

### Azure OpenAI の追加設定

`config.yaml` に以下を追記：

```yaml
llm:
  provider: azure_openai
  model: gpt-4o              # デプロイ名
  azure_endpoint: https://YOUR_RESOURCE.openai.azure.com/
  azure_deployment: gpt-4o
```

---

## 対応アクション一覧

エージェントが使用できるアクションの全一覧です。

### マウス・キーボード操作

```jsonc
{"action": "click",        "x": 320, "y": 450}
{"action": "double_click", "x": 320, "y": 450}
{"action": "right_click",  "x": 320, "y": 450}
{"action": "drag",         "x1": 100, "y1": 100, "x2": 400, "y2": 400}
{"action": "scroll",       "x": 500, "y": 300, "dir": "down", "amount": 3}
{"action": "type",         "text": "入力テキスト"}
{"action": "key",          "key": "enter"}           // ctrl+c, alt+f4 等も可
```

### テキスト・ファイルツール

```jsonc
{"action": "cmd",             "command": "dir C:\\Users", "timeout": 30}
{"action": "file_read",       "path": "C:/foo.txt"}
{"action": "file_write",      "path": "C:/foo.txt", "content": "...", "mode": "overwrite"}
// mode: "overwrite"（上書き）/ "append"（追記）
{"action": "dir_list",        "path": "C:/project"}
{"action": "clipboard_read"}
{"action": "clipboard_write", "text": "..."}
{"action": "get_windows"}
{"action": "get_processes"}
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

## プロジェクト構成

```
operant/
├── agent/
│   ├── core.py          # メインエージェントループ（LLM呼び出し・パース・アクション実行）
│   ├── screenshot.py    # スクショ取得・差分検出（SSIM）・WebP変換
│   ├── controller.py    # マウス・キーボード操作（pyautogui）
│   ├── tools.py         # テキスト直接処理ツール群（cmd・ファイル・クリップボード等）
│   ├── context.py       # 会話履歴管理・要約・刈り込み
│   └── __init__.py
├── llm/
│   ├── base.py          # 抽象基底クラス・システムプロンプト・ファクトリ
│   ├── claude.py        # Anthropic Claude 実装
│   ├── openai.py        # OpenAI / Azure OpenAI 実装
│   ├── gemini.py        # Google Gemini 実装
│   ├── ollama.py        # Ollama ローカル LLM 実装
│   └── __init__.py
├── web/
│   ├── server.py        # FastAPI + WebSocket + 認証
│   ├── static/
│   │   ├── index.html   # メインチャット画面
│   │   ├── login.html   # ログイン画面
│   │   ├── app.js       # フロントエンド JS（WebSocket通信）
│   │   └── style.css    # スタイル
│   └── __init__.py
├── i18n/
│   ├── ja.yaml          # 日本語リソース
│   ├── en.yaml          # 英語リソース
│   ├── zh.yaml          # 中国語（簡体）リソース
│   └── ko.yaml          # 韓国語リソース
├── logs/                # 実行ログ（自動作成）
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
| **緊急停止** | Web パネル上部の緊急停止ボタンで即時ループ停止 |
| **pyautogui フェイルセーフ** | マウスを画面左上（0,0）に移動すると自動停止 |
| **コマンドタイムアウト** | `cmd` アクションはデフォルト 30 秒でタイムアウト |
| **出力サイズ上限** | コマンド出力は上限文字数でトリミング（LLM への過大送信を防止） |
| **OPERANT.md 禁止操作** | システムファイル・レジストリ書き込みをデフォルトで禁止定義 |
| **web_fetch 制限** | オプション機能。有効時も HTML を Markdown 変換・上限文字数トリミング後に渡す |

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

**原因:** 依存パッケージがインストールされていない、または仮想環境が有効になっていない。

**解決策:**

```bash
# 仮想環境が有効か確認（プロンプトに (.venv) が表示されているか）
.venv\Scripts\activate

# 再インストール
pip install -r requirements.txt
```

---

#### `config.yaml not found. Starting setup wizard...` が毎回表示される

**原因:** `config.yaml` が存在しないか、セットアップが完了していない。

**解決策:**

```bash
python main.py --setup
```

ウィザードを最後まで完了させると `config.yaml` が生成されます。

---

#### `ERROR: config.yaml is empty or invalid.`

**原因:** `config.yaml` が破損しているか、YAML 形式が正しくない。

**解決策:**

```bash
# 設定をリセットして再セットアップ
del config.yaml
python main.py
```

---

### LLM API のエラー

---

#### `LLM error: AuthenticationError` / `Invalid API Key`

**原因:** API キーが正しくない、または期限切れ。

**解決策:**

1. 各プロバイダーのダッシュボードで API キーを確認
2. `python main.py --setup` で API キーを再設定（接続テストが自動実行される）
3. 環境変数を使用している場合は設定を確認：
   ```powershell
   echo $env:ANTHROPIC_API_KEY
   ```

---

#### `LLM error: RateLimitError`

**原因:** API のレート制限（リクエスト数・トークン数の上限）に達した。

**解決策:**

1. しばらく待ってから再試行
2. API プランのアップグレードを検討
3. `config.yaml` の `max_tokens` を小さくして消費を抑える：
   ```yaml
   llm:
     max_tokens: 128   # デフォルト 256 から削減
   ```

---

#### `LLM error: Connection timeout` / `httpx.ConnectTimeout`

**原因:** インターネット接続が不安定、または API サーバーへの疎通不良。

**解決策:**

1. インターネット接続を確認
2. VPN 使用中の場合は一時的に無効化して試す
3. プロキシ環境の場合は環境変数を設定：
   ```powershell
   $env:HTTPS_PROXY = "http://proxy.example.com:8080"
   ```

---

#### `Task timeout (300s)`

**原因:** エージェントのループが 300 秒（5 分）を超えた。

**解決策:**

`config.yaml` でタイムアウトを延長：

```yaml
agent:
  loop_timeout: 600   # 10分に延長
```

---

### スクリーンショット・操作のエラー

---

#### `pyautogui.FailSafeException: PyAutoGUI fail-safe triggered`

**原因:** マウスカーソルが画面左上（0, 0）に移動したため、フェイルセーフが発動した。

**解決策:**

これは正常な安全機能です。エージェントが意図しない操作を行った際の停止手段として機能しています。再度タスクを指示して再開してください。

---

#### スクリーンショットが真っ黒になる

**原因:** セキュリティ保護されたウィンドウ（UAC ダイアログ、DRM コンテンツ等）や、画面がロックされている。

**解決策:**

1. 管理者権限でターミナルを起動して `python main.py` を実行
2. 対象のアプリが最小化されていないか確認
3. Windows のディスプレイ設定でハードウェアアクセラレーションを確認

---

#### クリック座標がずれる

**原因:** 複数モニター環境や、スケーリング設定（125%・150% 等）が影響している場合がある。

**解決策:**

1. `config.yaml` のスクリーンショット解像度設定を実際の画面解像度に合わせる：
   ```yaml
   screenshot:
     max_width: 1920
     max_height: 1080
   ```
2. Windows の表示スケーリングを 100% に設定
3. プライマリモニターの解像度設定を確認

---

#### `pywinauto` 関連のエラー（`get_ui_text` が失敗する）

**原因:** 対象ウィンドウが Accessibility API に対応していない（例: ゲーム、一部の Electron アプリ）。

**解決策:**

この場合は自動的にスクリーンショット経由にフォールバックします。OPERANT.md に以下を追記すると明示的に指定できます：

```markdown
## カスタムルール
- get_ui_text が失敗した場合は screenshot を使用すること
```

---

### Web パネルのエラー

---

#### ブラウザで `http://localhost:8765` に接続できない

**原因:** サーバーが起動していない、またはポートが使用中。

**解決策:**

1. `python main.py` がエラーなく起動しているか確認
2. 別のポートを試す：
   ```yaml
   web:
     port: 8766
   ```
3. ファイアウォールの設定を確認：
   ```powershell
   # 管理者権限で実行
   netsh advfirewall firewall add rule name="Operant" dir=in action=allow protocol=TCP localport=8765
   ```

---

#### ログイン後に即座にログアウトされる / セッションが維持されない

**原因:** ブラウザのプライベートモード、または Cookie がブロックされている。

**解決策:**

1. 通常のブラウザウィンドウ（プライベートモード以外）でアクセス
2. ブラウザの設定で `localhost` の Cookie を許可
3. `config.yaml` でセッション期限を確認：
   ```yaml
   web:
     session_expire_hours: 24
   ```

---

#### パスワードを忘れた

**解決策:**

セットアップを再実行してパスワードをリセットします：

```bash
python main.py --setup
```

---

#### WebSocket が切断される / チャットがリアルタイムで更新されない

**原因:** ネットワークの問題、またはプロキシが WebSocket をブロックしている。

**解決策:**

1. ページを再読み込み（F5）
2. 別のブラウザで試す（Chrome / Edge / Firefox）
3. ブラウザの開発者ツール（F12）→ コンソールタブでエラーを確認

---

### ログの確認方法

問題が解決しない場合は、ログファイルを確認してください：

```
logs/operant.log
```

ログレベルを `DEBUG` に変更してより詳細な情報を出力する場合は、`main.py` の以下の行を変更：

```python
# 変更前
logging.basicConfig(level=logging.INFO, ...)

# 変更後
logging.basicConfig(level=logging.DEBUG, ...)
```

---

## 今後の予定

以下は現バージョンのスコープ外として検討中の機能です：

- タスクのスケジューリング・自動実行
- ブラウザ拡張機能との連携（DOM 直接取得）
- 2段階 LLM（軽量モデルと高精度モデルの自動切り替え）
- Web パネルでの `config.yaml` 設定 UI

---

## 変更履歴

### v0.3.0（latest）

- **LLM 生成中インジケーター** — エージェントが LLM に問い合わせ中に「生成中...」アニメーションをチャット上に表示。エージェントの動作状態が一目でわかる
- **アクションログのチャット表示** — 実行中のアクション（クリック・コマンド実行等）をチャット画面に薄いログとして表示。何をしているかを逐次確認可能
- **ステップカウンター** — ヘッダーで現在タスクの思考ターン数をリアルタイム表示
- **メッセージタイムスタンプ** — 各メッセージにホバーで表示される受信時刻を追加
- **コピーボタン** — メッセージにホバー時にコピーボタンを表示。内容をワンクリックでクリップボードへ
- **スクリーンショットダウンロード** — スクリーンショットペインの右下にダウンロードボタンを追加。最新画像を WebP で保存可能
- **WebSocket 接続状態インジケーター** — ヘッダーのドットインジケーターで接続状態（緑: 接続中、橙: 接続試行中、赤: 切断）を常時表示

### v0.3.0（2026-03-17）

- **Ollama（ローカル LLM）対応** — `provider: ollama` 設定で Ollama を使用可能。API キー不要で完全ローカル実行。Vision 対応モデル（llava 等）でスクリーンショット操作も対応
- **OPERANT.md 編集 UI** — Web パネルのヘッダーに「ルール編集」ボタンを追加。ブラウザ上でエージェントルールを直接編集・保存可能
- **多言語対応の拡充** — 中国語（簡体）・韓国語を追加。セットアップウィザードで選択可能（OS ロケールによる自動検出にも対応）

---

## ライセンス

MIT License

---

## 貢献・フィードバック

バグ報告・機能要望は Issue でお気軽にどうぞ。
Pull Request も歓迎します。
