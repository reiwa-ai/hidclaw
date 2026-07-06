# HIDClaw の使い方

この文書では、HIDClaw の起動、WebUI 操作、設定ファイル、メール通知、Discord 操作をまとめます。対象 PC には専用ソフトウェアを入れません。Pi 5 と Pico / Pico 2 を接続し、Pi 5 側で操作プログラムを起動します。

Pico / Pico 2 には予めpico/build/firmware.uf2を転送しておきます。

## 1. 接続

```text
対象 PC HDMI OUT -> USB HDMI Capture Board -> Raspberry Pi 5
対象 PC USB IN   <- Pico USB Device
Pi5 GPIO UART    -> Pico UART
```

UART 配線:

```text
Raspberry Pi 5 GPIO14 TXD -> Pico GP1 / UART0 RX
Raspberry Pi 5 GPIO15 RXD <- Pico GP0 / UART0 TX
Raspberry Pi 5 GND        <-> Pico GND
```

Pi 5 側の既定値:

```text
HDMI capture: /dev/video0
UART:         /dev/serial0
baudrate:     115200
WebUI:        127.0.0.1:8080
```

## 2. 起動コマンド

WebUI を起動します。

```sh
python3 pi/app.py --mode web
```

設定ファイルを書き換えて起動します。

```sh
cp config/example.toml config/local.toml
vim onfig/local.toml
... edit configure ...
python3 pi/app.py --mode web --config config/local.toml
```

LAN 内の別端末から開く場合は、設定ファイルの `[app].bind_host` を Pi 5 の LAN 側 IP にするか、起動時に `--host` を指定します。

```sh
python3 pi/app.py --mode web --config config/local.toml --host 192.168.11.6 --port 8080
```

Discord 操作だけを起動し、WebUI の HTTP サーバーを開かない場合:

```sh
python3 pi/app.py --mode discord --config config/local.toml
```

Discord 接続を 1 回だけ確認して終了する場合:

```sh
python3 pi/app.py --mode discord --config config/local.toml --discord-once
```

Computer Use の CLI 確認:

```sh
OPENAI_API_KEY=... python3 pi/controller.py "open browser"
OPENAI_API_KEY=... python3 pi/controller.py --execute "open browser"
OPENAI_API_KEY=... python3 pi/controller.py --planning --execute "open browser and open notepad"
```

スクリーンショットだけ保存する場合は API キー不要です。

```sh
python3 pi/controller.py --capture-only --save-screenshot captures/check.png
```

Manual HID の CLI 確認:

```sh
python3 pi/hid_client.py PING
python3 pi/hid_client.py KEY WIN+R
python3 pi/hid_client.py TEXT hello
```

主な `pi/app.py` オプション:

```text
--mode web|discord
--config <toml>
--host <bind address>
--port <port>
--debug
--discord-once
```

主な `pi/controller.py` オプション:

```text
--capture-only
--save-screenshot <path>
--execute
--planning
--approve-risk
--config <toml>
--model <model>
--api-key-env <env>
--max-steps <n>
--device <path>
--port <path>
--baudrate <n>
--timeout <sec>
```

## 3. WebUI の基本操作

ブラウザで以下を開きます。

```text
http://127.0.0.1:8080/
```

`Screen` には対象 PC の現在画面が表示されます。`Refresh` を押すと HDMI キャプチャーデバイスから最新フレームを取得します。表示されない場合は、HDMI 接続、USB HDMI キャプチャーボード、対象 PC の外部ディスプレイ認識状態を確認してください。

### Request

Request は、自然言語の指示をそのまま Computer Use API に渡して対象 PC を操作する通常モードです。

最小サンプル:

```text
open browser
```

期待動作:

```text
Pi 5 が現在画面をキャプチャーし、Computer Use API に操作を問い合わせる。
返ってきた keypress / type / wait などの操作を Pico 経由で対象 PC に送る。
対象 PC でブラウザが起動する。
```

実行中は `Current Status` に `Computer Use API calling`、`Sending command to Pico`、`Waiting for result` などが表示されます。通常の PC 操作はまず Request を使います。

### Plan

Plan は、自然言語の指示をいったん複数ステップの計画に分解してから、各ステップを通常の Computer Use 実行に渡すモードです。

最小サンプル:

```text
open browser and then open notepad
```

期待動作:

```text
OpenAI API が「ブラウザを開く」「メモ帳を開く」のような短い計画を作る。
各ステップが順番に Computer Use API へ渡される。
高リスクまたは承認が必要と判定された計画は実行前に approval pending になる。
```

Plan は低レベル HID コマンドを作りません。`KEY WIN+R` のような直接コマンドは Manual HID で送ります。

### Manual HID

Manual HID は、デバッグ用に Pico へ低レベル UART/HID コマンドを直接送るモードです。自然言語ではありません。

最小サンプル:

```text
PING
KEY WIN+R
TEXT notepad
KEY ENTER
```

期待動作:

```text
PING は対象 PC へ入力せず、Pico の ACK だけを確認する。
KEY WIN+R は Windows の「ファイル名を指定して実行」を開く。
TEXT notepad は ASCII 文字列を入力する。
KEY ENTER は Enter キーを押す。
```

対応コマンド:

```text
TEXT <ascii text>
KEY <key>
KEY <modifier>+<key>
MOUSE_MOVE <x> <y>
CLICK LEFT
CLICK RIGHT
PING
```

主な制限:

```text
TEXT 本文は最大 256 文字
Pi 5 側は長い TEXT を 20 文字ごとに分割して ACK を待つ
TEXT は printable ASCII のうち現在の変換テーブルで扱える文字のみ
KEY は ENTER / ESC / BACKSPACE / TAB / SPACE / DELETE / F1-F12 / 英数字など
修飾キーは WIN / GUI / META / CMD / CTRL / CONTROL / SHIFT / ALT
MOUSE_MOVE は相対移動のみで、x/y は -100 から 100
CLICK は LEFT / RIGHT のみ
```

### Emergency Stop / Suspend / Resume

`Emergency Stop` は非常停止です。実行中または承認待ちの操作を止め、以後の HID 送信をブロックします。再開したい場合は、新しいコマンドを送って新しい操作として始めます。

`Suspend` は一時停止です。HID コマンド送信を止め、`Resume` で解除します。非常停止中は `Resume` できません。

## 4. 設定ファイル

設定ファイルは TOML 形式です。サンプルは `config/example.toml` にあります。通常はコピーして `config/local.toml` を作り、秘密情報はリポジトリに保存しません。

```sh
cp config/example.toml config/local.toml
```

起動時に指定します。

```sh
python3 pi/app.py --mode web --config config/local.toml
python3 pi/app.py --mode discord --config config/local.toml
python3 pi/controller.py --config config/local.toml --execute "open browser"
```

最小例:

```toml
[app]
mode = "web"
bind_host = "127.0.0.1"
bind_port = 8080
default_planning = false
approval_timeout_seconds = 300.0
runtime_dir = "runtime"

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

[openai]
api_key_file = "/home/nama/openai-api-key.txt"
api_key_env = "OPENAI_API_KEY"
model = "gpt-5.5"
planning_model = "gpt-5.5"
api_timeout = 60.0
max_action_turns = 5

[logs]
database = "runtime/app.db"
screenshot_dir = "runtime/screenshots"
max_memory_logs = 100
max_screenshots = 5000
max_storage_mb = 1024
```

WebUI と Plan は `[openai].api_key_file` が存在すればそのファイルを優先し、なければ `[openai].api_key_env` の環境変数を読みます。`pi/controller.py` の単発 CLI は環境変数 `OPENAI_API_KEY` を使います。

Pi 5 に API キーファイルを置く例:

```sh
printf '%s\n' 'sk-...' > /home/nama/openai-api-key.txt
chmod 600 /home/nama/openai-api-key.txt
```

## 5. メール通知

メール通知は既定で無効です。承認要求、完了、非常停止、エラー、サスペンド、レジュームなどの状態変化を通知できます。

設定例:

```toml
[email]
enabled = true
delivery = "smtp"
smtp_account_file = "/home/nama/mail-send-vert.txt"
to_addrs = ["operator@example.com"]
min_interval_sec = 300.0
rate_limit_per_hour = 10
attachment_limit_mb = 10
```

外部 SMTP へ送らず、コンソール出力だけで確認する場合:

```toml
[email]
enabled = true
delivery = "console"
smtp_account_file = "/home/nama/mail-send-vert.txt"
to_addrs = []
```

`to_addrs` が空の場合は、SMTP アカウントファイルの `SENDER_MAIL` 宛に送ります。

Pi 5 に保存する SMTP アカウントファイルの形式:

```text
STARTTLS=true
SMTP_SERVER=smtp.example.com
SMTP_PORT=587
SENDER_MAIL=sender@example.com
SMTP_PASSWORD=your-smtp-password
```

ファイルは UTF-8 テキストです。`=` と `:` のどちらの区切りも扱えます。パスワードはログへ残しません。

```sh
chmod 600 /home/nama/mail-send-vert.txt
```

## 6. Discord 操作

Discord 操作は既定で無効です。Bot が指定チャンネルをポーリングし、新しいコマンドだけを実行します。安全のため、ギルド、チャンネル、ユーザーの allowlist を必ず設定します。

設定例:

```toml
[discord]
enabled = true
token_file = "/home/nama/discord-api-key.txt"
bot_name = "AgentDev"
bot_user_id = "123456789012345678"
guild_id = "..."
channel_id = "..."
allowed_guild_ids = ["..."]
allowed_channel_ids = ["..."]
allowed_user_ids = ["..."]
poll_interval_sec = 5.0
poll_limit = 20
skip_existing_on_startup = true
max_command_age_sec = 60.0
api_timeout = 15.0
rate_limit_per_hour = 20
attachment_limit_mb = 8
```

Bot token は Pi 5 のファイルへ保存します。

```sh
printf '%s\n' 'YOUR_DISCORD_BOT_TOKEN' > /home/nama/discord-api-key.txt
chmod 600 /home/nama/discord-api-key.txt
```

### Discord bot の作り方

1. Discord Developer Portal で New Application を作成します。
2. Bot を追加し、Token を発行して `/home/nama/discord-api-key.txt` に保存します。
3. Bot 設定で Message Content Intent を有効にします。
4. OAuth2 の URL Generator で `bot` scope を選びます。
5. Bot Permissions に `View Channels`、`Read Message History`、`Send Messages`、`Attach Files` を付けて招待 URL を作ります。
6. Bot を対象サーバーに招待します。
7. Discord の Developer Mode を有効にし、サーバー ID、チャンネル ID、自分のユーザー ID、Bot ユーザー ID を Copy ID で取得します。
8. 取得した ID を `[discord]` の `allowed_guild_ids`、`allowed_channel_ids`、`allowed_user_ids`、`bot_user_id` に設定します。

`bot_user_id` は `<@123...>` のようなメンションを解釈するための ID です。分からない場合は、Bot をサーバーに参加させたあと、Bot ユーザーを右クリックして Copy ID した値を入れてください。空のままでも `@AgentDev` というテキスト形式の呼びかけは扱えます。

### Discord 起動

WebUI と同時に Discord worker を動かす場合:

```sh
python3 pi/app.py --mode web --config config/local.toml
```

Discord だけ動かす場合:

```sh
python3 pi/app.py --mode discord --config config/local.toml
```

接続確認:

```sh
python3 pi/app.py --mode discord --config config/local.toml --discord-once
```

### Discord コマンド

通常は Bot へのメンションで送ります。

```text
@AgentDev open browser
@AgentDev request: open browser
@AgentDev hid: KEY WIN+R
@AgentDev screen
@AgentDev stop
@AgentDev approve
@AgentDev reject
```

意味:

```text
@AgentDev open browser
  Plan 付き Request として実行する既定形式。

@AgentDev request: open browser
  明示的な Request。Plan 付きで実行される。

@AgentDev hid: KEY WIN+R
  Manual HID として低レベルコマンドを直接送る。

@AgentDev screen
  最新スクリーンショットを Discord に送る。

@AgentDev stop
  Emergency Stop を実行する。

@AgentDev approve
  承認待ちの操作を承認する。

@AgentDev reject
  承認待ちの操作を拒否する。
```

テスト互換として `/screen`、`/request open browser`、`/approve`、`/reject` 形式も受け付けます。

## 7. ログと保存先

既定ではログとスクリーンショットは `runtime/` 配下に保存されます。

```text
runtime/app.db
runtime/screenshots/
```

WebUI の Logs 画面では、ユーザー入力ログ、実際の操作ログ、システムログ、トークン使用量を確認できます。スクリーンショットは `max_screenshots` と `max_storage_mb` の設定に従って整理されます。

## 8. 安全上の注意

HIDClaw は対象 PC を実際に操作します。実行前に、対象 PC に秘密情報が保存されていないこと、操作してよい状態であることを確認してください。

対象PCのスクリーンキャプチャが外部に送信されるので、企業所有のPCなど利用ポリシーが設定されているPCは、ポリシーに違反しないよう注意してください。

WebUI は LAN 内運用を想定しています。認証なしでインターネットへ直接公開しないでください。Discord 操作は allowlist を必ず設定し、Bot token、OpenAI API key、SMTP password をリポジトリに保存しないでください。

## 9. 免責事項

HIDClaw は「ASIS」で提供されます。HIDClaw を使用した事によるいかなる損害にも作者は責任を持ちません。この免責事項には、操作対象PCに対する物理的な破壊、操作対象PCに保存されているデータの流出、操作対象PCの利用ポリシー/利用規約違反等による損害賠償請求も含まれますがそれに限りません。HIDClaw が行う操作対象PCへの操作について、作者は一切関与せず、利用者が全責任を負うものとします。

