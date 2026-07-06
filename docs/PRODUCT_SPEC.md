# Pico HID Bridge 本開発仕様

この文書は、Pico HID Bridge の要求仕様と詳細仕様を整理するための仕様書です。README.md は利用者向けの概要、ハードウェア構成、WebUI の使い方に限定し、開発時の制約や作業ルールは AGENT.md に置きます。

## 1. 目的とスコープ

Pico HID Bridge は、対象 PC に専用ソフトウェアをインストールせず、外部ハードウェアだけで画面観測とキーボード・マウス操作を行うシステムです。

対象 PC からは、以下の通常デバイスとして認識される構成を維持します。

```text
- HDMI 出力先の外部ディスプレイ
- USB HID Keyboard
- USB HID Mouse
```

Raspberry Pi 5 は HDMI キャプチャーで対象 PC の画面を観測し、Raspberry Pi Pico / Pico 2 は USB HID デバイスとして対象 PC へ入力を送信します。Pi 5 と Pico の間は UART で接続します。

## 2. 現在の開発ステージ

```text
ステージ: 本開発
完了済み基盤: Pico HID Keyboard / Mouse、UART、HDMI Capture、OpenAI Computer Use API 最小プローブ、Flask WebUI 最小実装
方針: 機能ごとに小さく実装し、実機確認を挟む
```

本開発では、一度に全機能を実装しません。PC 操作、通知、外部チャット連携、LLM 判断、長時間実行は事故時の影響が大きいため、段階的に実装します。

## 3. 要求仕様

### 3.1 基本要求

```text
FR-001 対象 PC に専用ソフトウェアをインストールしない。
FR-002 Pico は対象 PC から通常の USB HID Keyboard / Mouse として認識される。
FR-003 Pi 5 は対象 PC の HDMI 出力を USB HDMI キャプチャーボードで取得する。
FR-004 Pi 5 は Pico へ UART で操作コマンドを送信する。
FR-005 Pico は UART で受信したコマンドを HID キーボード・マウス入力に変換する。
FR-006 Pi 5 は WebUI から現在画面を表示できる。
FR-007 Pi 5 は WebUI の Request 入力から Computer Use API を通じて対象 PC を操作できる。
FR-007a Pi 5 は WebUI の Manual HID 入力からデバッグ用の低レベル HID コマンドを送信できる。
FR-008 WebUI / CLI / 将来の Discord 操作から非常停止できる。
FR-009 ユーザー入力ログと PC 操作ログを分離して保存できる。
FR-010 主要イベント時にスクリーンキャプチャを保存できる。
FR-011 OpenAI API を使い、画面理解、操作提案、プランニング、リスク判定を行える。
FR-012 プランニング機能は既定 OFF とし、明示的に ON にした場合のみ使う。
FR-013 高リスク操作は実行前に承認を要求する。
FR-014 メールと Discord で状態通知できる。
FR-015 長時間操作では進捗表示、警告、サスペンド、レジュームを提供する。
FR-016 API トークン使用量と予測量を表示し、予算超過を制御できる。
```

### 3.2 非機能要求

```text
NFR-001 安全性を優先し、LLM の判断だけに依存しない。
NFR-002 非常停止は常に最優先で処理する。
NFR-003 秘密情報をリポジトリに保存しない。
NFR-004 WebUI は LAN 限定アクセスを目標とし、インターネットへ直接公開しない。
NFR-005 Discord 操作は許可ギルド、チャンネル、ユーザー、ロールを限定する。
NFR-006 ログとスクリーンショットは設定ファイルで指定できる容量上限、保持期間、重複抑制を持つ。
NFR-007 実装は小さな実機確認ステップへ分割する。
NFR-008 既存の確認済み物理 I/O 経路を壊さない。
NFR-009 samples/ は参照用であり、直接改造しない。
NFR-010 Pico ビルド環境と Zephyr SDK 環境は勝手に変更しない。
```

### 3.3 安全要求

```text
SAFE-001 非常停止後は実行中または承認待ちの操作を停止し、次の新規コマンドを新しい操作として扱う。
SAFE-002 承認待ち中は PC 操作を進めない。
SAFE-003 ファイル削除、上書き、保存、送信、投稿、購入、決済は承認必須にする。
SAFE-004 ログイン、認証、パスワード入力、個人情報入力は承認必須にする。
SAFE-005 設定変更、インストール、アンインストールは承認必須にする。
SAFE-006 長時間操作プラン、未知操作、高リスク操作は承認必須にする。
SAFE-007 非常停止、エラー、承認要求、操作前後はスクリーンキャプチャを保存する。
SAFE-008 通知はレート制限と重複抑制を持つ。
SAFE-009 Pico 側にも将来的に PANIC STOP または watchdog を追加する。
```

## 4. 詳細仕様

### 4.1 システム構成

```text
Raspberry Pi 5
├─ Core Controller
│  ├─ CLI mode
│  ├─ WebUI mode Flask server
│  └─ Discord bot mode
│
├─ Capture Service
│  ├─ /dev/video0 frame capture
│  ├─ latest screenshot cache
│  └─ event screenshot capture
│
├─ HID Command Service
│  └─ /dev/serial0 UART to Pico
│
├─ Planning Service
│  ├─ OpenAI API planning
│  ├─ approval-risk classification
│  └─ token usage tracking
│
├─ Operation Log Service
│  ├─ user input log
│  ├─ PC operation log
│  ├─ approval log
│  ├─ notification log
│  ├─ token usage log
│  └─ screenshot log
│
├─ Notification Service
│  ├─ email
│  └─ Discord status updates
│
└─ Runtime State Service
   ├─ emergency stop
   ├─ suspend / resume
   ├─ progress tracking
   └─ approval waiting state

Raspberry Pi Pico / Pico 2
└─ USB HID Keyboard / Mouse + UART command receiver
```

Pi 5 側のコードは、機能追加しやすいように `pi/pico_hid_bridge/` パッケージへ共通機能を分離する。`pi/` 直下の Python ファイルは、SSH 手順や既存コマンド互換のための薄いエントリポイントにする。

```text
pi/
├─ app.py                    WebUI 互換エントリポイント
├─ controller.py             CLI / Computer Use probe 互換エントリポイント
├─ run_e2e_case.py           E2Eケース実行互換エントリポイント
├─ run_e2e_suite.py          E2Eまとめ実行互換エントリポイント
├─ tools/                    テスト・動作確認用CLI実体
└─ pico_hid_bridge/
   ├─ cli/
   │  └─ controller.py       Computer Use probe 実装
   ├─ e2e/
   │  ├─ cases.py            E2Eケース定義
   │  ├─ model.py            E2Eケース/ステップのデータ構造
   │  └─ runner.py           E2E共通ランナー
   ├─ web/
   │  ├─ app.py              Flask WebUI 実装
   │  └─ templates.py        WebUI HTML/CSS/JavaScript
   ├─ config.py              設定ロード
   ├─ capture.py             HDMIキャプチャと画像エンコード
   ├─ hid.py                 UART HIDコマンド生成・検証・送信
   ├─ computer_use.py        Computer Use API 共通処理
   ├─ actions.py             Computer Use action から HID 実行への変換とイベントフック
   ├─ notifications.py       email / Discord 連携用の通知フック
   └─ paths.py               パス解決
```

WebUI、CLI、E2E、将来の Discord bot は、直接低レベル処理を持たず、共通パッケージを呼び出す。メール送信、Discord通知、承認要求、ログ永続化は `actions.py` の `PipelineEvent` / `EventSink` を通して追加する。

WebUI mode keeps HDMI capture open through a single `CaptureService` thread for the lifetime of `app.py`. `/api/screenshot` and Computer Use screenshot responses use the latest in-memory frame from that service. One-shot capture helpers remain available for CLI capture-only and non-WebUI probes.

### 4.2 ハードウェア仕様

UART:

```text
Raspberry Pi 5 GPIO14 TXD → Pico GP1 / UART0 RX
Raspberry Pi 5 GPIO15 RXD ← Pico GP0 / UART0 TX
Raspberry Pi 5 GND        ↔ Pico GND
baudrate                  115200
voltage                   3.3V
```

映像と HID:

```text
対象 PC HDMI OUT → USB HDMI Capture Board → Raspberry Pi 5 /dev/video0
対象 PC USB IN   ← Pico USB HID Keyboard / Mouse
```

### 4.3 Pico UART コマンド仕様

現在の実装済みコマンド:

```text
TEXT <ascii text>
KEY <key>
KEY <modifier>+<key>
MOUSE_MOVE <x> <y>
CLICK LEFT
CLICK RIGHT
PING
```

制限:

```text
- UART 1行は最大 261 ASCII bytes（`TEXT ` prefix + 256文字 + 改行）
- TEXT 本文は最大 256文字
- Pi 5 側の送信実装は、長い TEXT を 20文字ごとの複数 UART 行へ分割し、各チャンクの ACK を待ってから次を送る
- TEXT は printable ASCII のうち、現在の変換テーブルで扱える文字のみ
- KEY は ENTER / ESC / BACKSPACE / TAB / SPACE / DELETE / F1-F12 / 英数字などを扱う
- 修飾キーは WIN / GUI / META / CMD / CTRL / CONTROL / SHIFT / ALT を扱う。修飾キー単独押下と、修飾キー + 通常キー1つの組み合わせを扱う
- MOUSE_MOVE は相対移動のみ
- MOUSE_MOVE の x/y は -100 から 100
- CLICK は LEFT / RIGHT のみ
- PING は対象 PC へ HID 入力を送らず、Pico UART の復帰確認用に ACK だけを返す
- 未知コマンド、長すぎる行、不正引数でクラッシュしない
- Pico は各UARTコマンドの処理完了後に `PICO_HID_OK` または `PICO_HID_ERR` を返す。Pi 5 側はACKを受け取るまで次のUART行を送らない
```

対象 PC 側にはキーボード配列補正用ソフトウェアを入れません。Pico が USB HID キーボードをエミュレートする構成を前提とし、文字入力で配列差分が問題になった場合は Pico 側の HID usage 変換テーブルで吸収します。

将来追加候補:

```text
PANIC STOP
入力レート制限
watchdog
絶対座標移動または座標キャリブレーション
```

### 4.4 CLI mode

CLI から単発操作または計画操作を実行します。実装は `pi/pico_hid_bridge/cli/controller.py` に置き、`pi/controller.py` は既存手順互換のエントリポイントとして残します。

現在の主なオプション:

```text
--capture-only
--save-screenshot <path>
--execute
--model <model>
--api-key-env <env>
--max-steps <n>
--device <path>
--width <px>
--height <px>
--fps <n>
--warmup-frames <n>
--min-brightness <value>
--ready-timeout <sec>
--port <path>
--baudrate <n>
--timeout <sec>
```

既定動作:

```text
execute: OFF
OpenAI API を使う場合は OPENAI_API_KEY が必要
capture-only では API キー不要
```

`--execute` を付けた場合のみ、Computer Use の提案操作のうち現在の Pico firmware が扱える操作を送信します。

### 4.5 WebUI mode

Flask で Web サーバーを立てます。

起動例:

```sh
python3 pi/app.py --mode web --config config/example.toml
```

既定:

```text
bind_host: 127.0.0.1
bind_port: 8080
planning:  false
```

最終的な運用目標は LAN 限定アクセスです。初期サンプルは安全側に倒して loopback にバインドし、LAN 内端末から使う場合は `config/local.toml` で Raspberry Pi 5 の LAN 側アドレスを明示します。

現在の WebUI 表示項目:

```text
- 現在のスクリーンキャプチャ
- Request タブ（Computer Use API 経由）
- Plan タブ（Planning付きのRequest送信）
- Manual HID タブ（低レベルデバッグ用）
- 指示送信ボタン
- 非常停止ボタン
- サスペンド / レジュームボタン
- 現在状態（Computer Use API呼び出し中、Picoへのコマンド送信中、結果待ちなど）
- 直近ユーザー入力ログ
- 直近操作ログ
```

将来追加する WebUI 表示項目:

```text
- 承認待ち操作
- トークン使用量
- スクリーンショット履歴
- 永続ログ検索
- 通知状態
```

WebUI の基本エンドポイント:

```text
GET  /                    WebUI
GET  /api/screenshot      現在のスクリーンキャプチャ
POST /api/command         Request 指示送信（Computer Use API 経由）
POST /api/manual-hid      Manual HID コマンド送信（低レベルデバッグ用）
POST /api/planning        プランニング状態切り替え
POST /api/emergency-stop  非常停止
POST /api/suspend         サスペンド
POST /api/resume          再開
POST /api/approve         承認
POST /api/reject          否認
GET  /api/status          状態取得
GET  /api/logs/user       ユーザー入力ログ
GET  /api/logs/operation  PC操作ログ
GET  /api/tokens          トークン使用量
```

WebUI は LAN 内運用を想定します。ただし、認証なしで外部公開しません。初期本開発版では localhost または Raspberry Pi 5 の LAN 側アドレスに限定します。

### 4.6 Discord bot mode

Discord の指定チャットルームから操作できるようにします。

最低限認識するコマンド:

```text
/screen
/request <instruction>
/stop
/status
/approve <id>
/reject <id>
```

機能:

```text
- 現在のスクリーンキャプチャをチャットに表示
- チャット入力を OpenAI API で操作コマンドまたは操作計画へ変換
- 非常停止
- 承認待ち通知
- 操作中の進捗通知
- 完了通知
```

最低限の防御:

```text
- 許可ギルドと許可チャンネルを限定
- 許可ユーザーまたはロールを限定
- 添付画像のサイズ制限
- 同一状態通知の抑制
- 非常停止も許可ユーザーのみ実行可能にするかは要確認
```

### 4.7 OpenAI API 利用仕様

API キーは環境変数または設定ファイルの環境変数名から読みます。秘密情報をリポジトリに保存しません。

```text
OPENAI_API_KEY
OPENAI_MODEL
```

利用目的:

```text
- Computer Use による画面理解と操作提案
- 複雑な指示の操作プランニング
- 操作リスク判定
- Discord チャット入力のコマンド変換
- 長時間プランの要約と進捗説明
```

プランニング機能は既定 OFF です。

```text
CLI:   --planning を指定したときのみ ON
WebUI: Plan タブから Request を送信したときのみ ON
Config: default_planning = false
```

### 4.8 プランニング仕様

プランニング機能は、ユーザーの自然言語指示を複数ステップの操作計画に変換します。

Stage05 時点では、プランニングは既存の Computer Use 実行経路の前段に置く薄いラッパーとして実装します。OpenAI API から JSON のステップ列を取得し、各ステップの自然言語指示を通常の `execute_computer_use_request` に順番に渡します。プランニング層は `KEY` / `TEXT` / `MOUSE_MOVE` / `CLICK` のような低レベル HID コマンドを生成しません。

プラン生成は汎用プロンプトを使い、テストシナリオ固有の指示をプロンプトへ埋め込んではいけません。実機 E2E でプラン品質に問題が出た場合は、まず汎用プロンプトを見直し、それでも薄いラッパーで収まらない場合だけ実装構造を見直します。

プランの最小フィールド:

```text
plan_id
created_at
user_instruction
planning_enabled
estimated_steps
estimated_duration_sec
estimated_token_usage
risk_level
requires_approval
steps[]
```

各ステップの最小フィールド:

```text
step_id
description
expected_screen_state
action_type
action_payload
risk_level
requires_approval
status
started_at
finished_at
```

長時間操作になりそうな場合:

```text
- estimated_duration_sec が設定値を超えたら警告
- estimated_steps が設定値を超えたら警告
- estimated_token_usage が設定値を超えたら警告
- WebUI / Discord / email に長時間操作予定を通知
- 実行前に明示承認を要求
```

### 4.9 承認仕様

悪影響がありそうな PC 操作は、実行前に承認を求めます。

承認要否の判定は OpenAI API に依頼できます。ただし LLM の判定だけに依存せず、ルールベースの強制承認条件を併用します。

強制承認条件:

```text
- ファイル削除、上書き、保存
- 送信、投稿、購入、決済
- ログイン、認証、パスワード入力
- 設定変更、アンインストール、インストール
- 外部サイトへの個人情報入力
- 長時間操作プラン
- 未知または高リスクと分類された操作
```

承認状態:

```text
pending
approved
rejected
expired
cancelled_by_emergency_stop
```

承認待ち中は PC 操作を進めません。非常停止は承認状態に関係なく常に有効です。

### 4.10 非常停止仕様

入力経路:

```text
- WebUI Emergency Stop
- CLI interrupt / stop command
- Discord /stop
- 将来の物理ボタン
```

非常停止時の動作:

```text
- 以後の HID コマンド送信を停止
- 実行中プランを stopped に変更
- 承認待ちを cancelled_by_emergency_stop に変更
- スクリーンキャプチャを保存
- operation log に記録
- WebUI / Discord / email へ通知
```

非常停止後に新しいコマンドが入力された場合は、過去の実行中プラン、承認待ち、進捗状態を引き継がず、新しい操作として開始します。専用の解除ボタンは置かず、新規コマンド入力を再開トリガーにします。

### 4.11 操作ログ仕様

ログ種別:

```text
user_input_log      ユーザー入力、送信元、planning設定
operation_log       実際に送信したPC操作、結果、エラー
approval_log        承認要求、承認/否認、期限切れ
notification_log    email / Discord 通知
token_usage_log     API呼び出しごとのトークン使用量
system_event_log    起動、終了、非常停止、サスペンド、再開
```

保存先候補:

```text
初期本開発: SQLite + ファイルシステム
将来拡張: MySQL / PostgreSQL
```

初期実装では SQLite を推奨します。Pi 5 単体で運用でき、トランザクションがあり、ログ検索と容量管理を実装しやすいためです。

ディレクトリ案:

```text
runtime/
├─ app.db
├─ screenshots/
│  ├─ latest.jpg
│  └─ events/
└─ exports/
```

既定のログDBパスは `runtime/app.db`。SQLite の実行時ファイルとして `runtime/app.db-wal` と `runtime/app.db-shm` が作られる場合がある。DBスキーマ変更後などにログDBを初期化する場合は、WebUI / `app.py` を停止したうえで、この3ファイルを削除する。E2E用の一時DBは各テストruntime配下に作られるため、テストDBもまとめて消す場合は `runtime/` 配下の `app.db*` を対象にする。

スクリーンキャプチャを保存する主要タイミング:

```text
- ユーザー指示受信時
- プラン作成後
- 承認要求時
- PC操作前
- PC操作後
- エラー発生時
- 非常停止時
- サスペンド時
- 再開時
- 完了時
```

容量爆発対策:

```text
- スクリーンショット保存枚数の上限
- 保存期間の上限
- runtime 全体の最大容量
- 画像サイズと JPEG 品質の制限
- 同一画面の重複保存抑制
- latest 画像と event 画像の分離
- 古いログの自動アーカイブまたは削除
- DB VACUUM / ローテーション
```

### 4.12 メール通知仕様

設定項目:

```toml
[email]
enabled = false
delivery = "smtp" # smtp | console
smtp_account_file = "/home/nama/mail-send-vert.txt"
to_addrs = [] # 空ならSMTPアカウント自身へ送る
min_interval_sec = 300
rate_limit_per_hour = 10
attachment_limit_mb = 10
```

メール送信対象:

```text
- 承認を必要としているとき
- 動作が終了したとき
- 非常停止
- 長時間操作プラン作成
- エラーで停止
- サスペンド
- 再開
- その他大きな状態変化
```

メール爆発対策:

```text
- enabled = false をデフォルトにする
- min_interval_sec を守る
- 同じ状態の連続通知を抑制する
- 1プランあたりの最大メール数を設ける
- 添付画像サイズを制限する
```

SMTP アカウントファイルは `STARTTLS`、`SMTP_SERVER`、`SMTP_PORT`、`SENDER_MAIL`、`SMTP_PASSWORD` のキーを持つUTF-8テキストです。秘密値はログへ残しません。SMTP送信結果は `notification_log` に `sent`、`failed`、`skipped`、`rate_limited` として記録します。`delivery = "console"` の場合はSMTP接続を行わず、送信内容をコンソールへ出力して `sent` として記録します。

### 4.13 Discord 通知・操作仕様

設定項目:

```toml
[discord]
enabled = false
token_env = "DISCORD_BOT_TOKEN"
guild_id = ""
channel_id = ""
allowed_user_ids = []
allowed_role_ids = []
min_status_interval_sec = 60
attach_screenshot = true
max_screenshot_width = 1280
```

Discord は操作経路にも通知経路にもなるため、権限管理を必須にします。

### 4.14 サスペンド / レジューム仕様

サスペンド時に保存するもの:

```text
- plan_id
- current_step_id
- completed_steps
- pending_approval
- latest_screen_capture
- token_usage
- user_instruction
- runtime flags
```

レジューム時:

```text
- 現在画面を再キャプチャ
- 保存時の期待画面との差分を確認
- 差分が大きければ再開前に承認を求める
- 非常停止状態なら再開しない
```

### 4.15 進捗表示仕様

表示項目:

```text
completed_steps / total_steps
current_step_description
estimated_percent
elapsed_time_sec
estimated_remaining_sec
current_state
approval_waiting
last_operation_result
```

WebUI と Discord では、パーセンテージと現在ステップを常に確認できるようにします。

### 4.16 トークン使用量仕様

OpenAI API の呼び出しごとに、消費トークン量を保存します。

表示項目:

```text
- 現在セッションの入力トークン
- 現在セッションの出力トークン
- 現在セッションの合計トークン
- プランごとの合計トークン
- 1日合計
- 予測トークン量
```

制限:

```text
- 1操作あたりの最大トークン予算
- 1プランあたりの最大トークン予算
- 1日あたりの最大トークン予算
- 予算超過時は承認待ちまたは停止
```

### 4.17 設定ファイル仕様

設定ファイルは `config/local.toml` を想定します。秘密値は直接保存せず、環境変数名を保存します。

例:

```toml
[app]
mode = "web"
bind_host = "127.0.0.1"
bind_port = 8080
default_planning = false
require_approval_default = true
runtime_dir = "runtime"

[openai]
api_key_env = "OPENAI_API_KEY"
model = "gpt-5.5"
planning_model = "gpt-5.5"
risk_model = "gpt-5.5"
max_tokens_per_operation = 20000
max_tokens_per_plan = 100000
computer_prompt = """
Use a keyboard-first strategy. Prefer screenshot, keypress, type, or wait. When opening an application, use WIN+R, type the program name, and press ENTER. When switching active applications or windows, use ALT+TAB or other keyboard shortcuts. Avoid mouse move, click, and double_click unless keyboard operation is clearly impossible.
"""

[capture]
device = "/dev/video0"
width = 0
height = 0
fps = 0
warmup_frames = 60
min_brightness = 5.0
ready_timeout = 5.0
save_width = 1280
jpeg_quality = 80

[hid]
port = "/dev/serial0"
baudrate = 115200
timeout = 0.5

[logs]
backend = "sqlite"
database = "runtime/app.db"
screenshot_dir = "runtime/screenshots"
retention_days = 14
max_screenshots = 5000
max_screenshot_mb = 1024
max_storage_mb = 1024
max_memory_logs = 100

[email]
enabled = false
delivery = "smtp"
smtp_account_file = "/home/nama/mail-send-vert.txt"
to_addrs = []
min_interval_sec = 300
rate_limit_per_hour = 10
attachment_limit_mb = 10

[discord]
enabled = false
token_env = "DISCORD_BOT_TOKEN"
guild_id = ""
channel_id = ""
allowed_user_ids = []
allowed_role_ids = []
min_status_interval_sec = 60
```

## 5. 現在の実装状況

実装済み:

```text
- Pico USB HID Keyboard
- Pico USB HID Mouse
- Pico UART 1行コマンド受信
- Pi 5 から /dev/serial0 への UART 送信
- HDMI キャプチャー表示とスクリーンショット保存
- Computer Use API 最小プローブ
- Flask WebUI 最小実装
- WebUI Request タブからの Computer Use API 経由操作
- WebUI Manual HID タブからの低レベル HID コマンド送信
- WebUI の非常停止フラグ
- WebUI のサスペンド / レジューム最小状態管理
- WebUI の直近メモリログ
- SQLite 永続ログ DB の初期実装
- user_input_log / operation_log / screenshot_log / error_log
- スクリーンショットログの最大保持数に基づく古いファイル整理
- 壊れた SQLite DB の退避と新規DB作成
- Pi 5 E2E ランナーの複数ステップケース定義
- 開発ステップ別 E2E テストシナリオ台帳
```

未実装または本開発で拡張するもの:

```text
- 承認フロー
- メール通知
- Discord 操作
- プランニング実行
- トークン予算管理
- 長時間操作の進捗、警告、サスペンド永続化、レジューム検証
- Pico 側 PANIC STOP / watchdog
- 追加キー、修飾キー、絶対座標移動、キャリブレーション
```

## 6. 推奨実装順

```text
Stage 1: Core分離
  - capture / hid / controller / logging のモジュール分離
  - 既存 CLI / WebUI 動作を維持

Stage 2: SQLite操作ログ
  - user_input_log（実装済み）
  - operation_log（実装済み）
  - screenshot log（実装済み）
  - error_log（実装済み）
  - 最大スクリーンショット保持数に基づく整理（実装済み）

Stage 3: 非常停止と状態管理
  - runtime state
  - emergency stop
  - suspend / resume の土台

Stage 4: WebUI拡張
  - 現在スクリーンキャプチャ
  - 指示入力
  - Stage01で確認した主要操作をWebUI Request経由でも同等に実行
  - 非常停止
  - ログ閲覧
  - 承認待ち表示

Stage 5: プランニング
  - WebUI Plan tab
  - OpenAI API planning wrapper
  - JSON step list
  - Existing Computer Use execution path per step
  - デフォルトOFF

Stage 6: 承認フロー
  - LLM risk判定
  - ルールベース強制承認
  - approve / reject

Stage 7: メール通知
  - email

Stage 8: 長時間操作
  - 進捗
  - サスペンド永続化
  - レジューム検証
  - 長時間プラン警告

Stage 9: トークン管理
  - 使用量表示
  - 予測
  - 予算制限

Stage 10: Discord操作
  - /screen
  - /request
  - /stop
  - /approve /reject
```

各 Stage はさらに小さな実機確認ステップへ分割します。E2E テストでは `StageN-ScenarioM` の複数ケースを用意し、機能を網羅しながら過去ステージの回帰確認を継続します。

## 7. 要確認事項

以下は、仕様を確定するためにユーザー確認が必要な項目です。

```text
Q-004 Discord の非常停止は全許可ユーザーに許可するか、管理者ロールだけに限定するか。
Q-006 操作承認の期限切れ時間を何秒または何分にするか。
Q-007 長時間操作の警告しきい値を、時間、ステップ数、予測トークン数でそれぞれいくつにするか。
Q-008 メール通知と Discord 通知のどちらを優先通知経路にするか。
Q-009 Pico 側に最初に追加したいキーは BACKSPACE / TAB / CTRL+L / CTRL+C / CTRL+V のどれか。
Q-011 マウス操作は相対移動中心でよいか、画面座標ベースの絶対移動を優先するか。
Q-012 OpenAI モデル名は設定ファイルの既定値として固定するか、環境変数優先にするか。
```
