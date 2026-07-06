# AGENT.md

このリポジトリは、Raspberry Pi 5 と Raspberry Pi Pico / Pico 2 を使って、対象 PC を物理 USB HID キーボード・マウスとして操作する本開発プロジェクトです。

README.md は利用者向けの概要、ハードウェア構成、WebUI の使い方に限定します。要求仕様と詳細仕様は `docs/PRODUCT_SPEC.md` に置き、開発時の制約と作業ルールはこの AGENT.md に置きます。

## 最重要ルール

本開発へ移行済みですが、実機での段階的な動作確認を最優先します。

Codex / AI エージェントは、一度に全機能を実装してはいけません。必ず小さいステップごとに変更し、人間がビルド、書き込み、配線、実機動作確認を行った後で次のステップへ進みます。

大きな仕様は `docs/PRODUCT_SPEC.md` にまとめます。実装時は、この仕様を小さな作業単位に分解します。

## 現在のステージ

```text
ステージ: 本開発
PoC完了: Pico HID Keyboard / Mouse、UART、HDMI Capture、OpenAI Computer Use API 最小プローブ
本開発で追加済み: Flask WebUI 最小実装
WebUI運用目標: LAN 限定アクセス
```

## 開発環境

Pico ファームウェアは Windows 上の Zephyr SDK 環境でビルドします。

Zephyr Workspace:

```text
C:\Users\sakam\.pico-sdk\zephyr_workspace
```

Pico 2 の主対象:

```cmd
cd C:\Users\sakam\.pico-sdk\zephyr_workspace

C:\Users\sakam\.pico-sdk\zephyr_workspace\venv\Scripts\west.exe build ^
    -p auto ^
    -b rpi_pico2/rp2350a/m33 ^
    ..\..\Documents\Work\AgentDev\pico
```

`west build` のボード指定:

```text
rpi_pico2/rp2350a/m33
```

Codex はビルド環境を変更しません。

禁止:

```text
- Zephyr Workspace の変更
- west のインストール
- Python 仮想環境の再作成
- SDK の更新
- board 名の変更
```

Pico firmware を変更した場合のみ、必要に応じてビルドし、確認用 UF2 を `pico/build/step<番号>.uf2` に保存します。

スクリーンキャプチャや E2E artifact を Windows 側へ持ち帰る場合、プロジェクトのルート直下には置きません。一時調査用は `captures/`、長期ナレッジとして残す代表画像は `docs/knowledge/screenshots/<stage>/` に置き、不要になった一時画像は削除します。

## 作業対象ディレクトリ

```text
samples/
```

Zephyr 公式サンプルのコピーを置く参照用ディレクトリ。直接改造しません。

```text
pico/
```

Pico / Pico 2 側の Zephyr プロジェクト。USB HID Keyboard / Mouse、UART 受信、HID レポート生成、安全制御を実装します。

```text
pi/
```

Raspberry Pi 5 側の Python コード。UART 送信、HDMI キャプチャー、CLI、WebUI、ログ、通知、OpenAI API 連携、Discord 連携を実装します。

共通処理は `pi/pico_hid_bridge/` パッケージへ置きます。WebUI、CLI、E2E、将来の Discord bot は、このパッケージを呼び出す薄いエントリポイントにします。

```text
pi/pico_hid_bridge/config.py        設定
pi/pico_hid_bridge/capture.py       HDMIキャプチャ
pi/pico_hid_bridge/hid.py           UART HID
pi/pico_hid_bridge/computer_use.py  Computer Use API
pi/pico_hid_bridge/actions.py       action実行とイベントフック
pi/pico_hid_bridge/notifications.py email / Discord 追加場所
pi/pico_hid_bridge/web/             WebUI実装とHTML/CSS/JavaScript
pi/pico_hid_bridge/cli/             CLI実装
pi/pico_hid_bridge/e2e/             E2Eケース定義とランナー
pi/tools/                           テスト・動作確認用CLI実体
```

```text
config/
```

設定ファイル例を置きます。秘密値は直接保存せず、環境変数名を保存します。

```text
docs/
```

要求仕様、詳細仕様、設計、運用ルールを置きます。

## 現在の実装状況

Pico:

```text
- USB HID Keyboard
- USB HID Mouse
- UART 1行コマンド受信
- 成功した UART コマンドごとの LED 点滅
- 長すぎる UART 行の破棄
- 未知コマンドでクラッシュしない防御
```

Pi 5:

```text
- pi/hid_client.py による UART 送信
- pi/capture_viewer.py による HDMI キャプチャー表示とスクリーンショット保存
- pi/controller.py による Computer Use API 最小プローブ
- pi/app.py による Flask WebUI 最小実装
- pico_hid_bridge.operation_log による SQLite 永続ログ
```

WebUI の現在機能:

```text
- 現在スクリーンキャプチャの手動更新
- Request タブからの Computer Use API 経由操作
- Manual HID タブからの低レベル HID コマンド送信
- プランニング ON/OFF 表示と状態記録
- 非常停止フラグによる以後の HID 送信ブロック
- サスペンド / レジュームの最小状態管理
- 直近ユーザー入力ログ / 操作ログ表示
- ユーザー入力、操作、スクリーンショット、エラーの SQLite 保存
```

## 仕様方針

詳細は `docs/PRODUCT_SPEC.md` を参照します。

本開発で追加する主要仕様:

```text
- Core 分離
- SQLite 操作ログ
- 非常停止と状態管理
- WebUI 拡張
- プランニング ON/OFF
- 承認フロー
- メール通知
- 長時間操作の進捗、警告、サスペンド、レジューム
- API トークン使用量表示と予測
- Discord 通知と操作
```

プランニング機能は既定 OFF です。

```text
CLI:   --planning を指定したときのみ ON
WebUI: トグルを ON にしたときのみ ON
Config: default_planning = false
```

## Pico 側の現在のコマンド仕様

実装済みコマンド:

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
- TEXT は printable ASCII のうち現在の変換テーブルで扱える文字のみ。対象PCの日本語キーボード配列差分は Pico 側の HID usage 変換テーブルで吸収する
- KEY は ENTER / ESC / BACKSPACE / TAB / SPACE / DELETE / F1-F12 / 英数字などを扱う
- 修飾キーは WIN / GUI / META / CMD / CTRL / CONTROL / SHIFT / ALT を扱う。修飾キー単独押下と、修飾キー + 通常キー1つの組み合わせを扱う
- MOUSE_MOVE は相対移動のみ
- MOUSE_MOVE の x/y は -100 から 100
- CLICK は LEFT / RIGHT のみ
- PING は対象 PC へ HID 入力を送らず、Pico UART の復帰確認用に ACK だけを返す
- Pico は各UARTコマンドの処理完了後に `PICO_HID_OK` または `PICO_HID_ERR` を返す。Pi 5 側はACKを受け取るまで次のUART行を送らない
```

今後追加候補:

```text
KEY BACKSPACE
KEY TAB
KEY CTRL+L
KEY CTRL+C
KEY CTRL+V
PANIC STOP
入力レート制限
WATCHDOG
```

## Pi 5 側の実行メモ

依存関係:

```text
pyserial>=3.5
opencv-python>=4.8
openai>=1.99.0
Flask>=3.0
```

インストール例:

```sh
python3 -m pip install -r pi/requirements.txt
```

UART 送信:

```sh
python3 pi/hid_client.py hello
python3 pi/hid_client.py PING
python3 pi/hid_client.py KEY ENTER
python3 pi/hid_client.py MOUSE_MOVE 20 -10
python3 pi/hid_client.py CLICK LEFT
```

HDMI キャプチャービューア:

```sh
python3 pi/capture_viewer.py
```

Computer Use プローブ:

```sh
python3 pi/controller.py "Do not control the computer. Describe exactly what is visible on the screen."
python3 pi/controller.py --capture-only --warmup-frames 60 --save-screenshot pi/captures/controller_check.png
python3 pi/controller.py --execute "input Hello and enter"
```

WebUI:

```sh
python3 pi/app.py --mode web --config config/example.toml
```

## テスト環境

Pi 5 実機を使ったテスト環境、SSH 接続先、テストスクリプト、最小 API 確認手順は `docs/TESTING.md` にまとめます。

開発ステップ別の E2E テストシナリオは `docs/TEST_SCENARIOS.md` にまとめます。各 Stage は `StageN-ScenarioM` の複数ケースで機能を網羅し、実装済みケースは回帰テストとして継続実行し、未実装ステージは `pending` の TDD ひな形として管理します。

TDD 用のテスト実装計画は `docs/TEST_IMPLEMENTATION_PLAN.md`、テストプログラムの詳細仕様は `docs/TEST_PROGRAM_SPEC.md` にまとめます。テスト仕様は本実装仕様と混同しないよう、`docs/PRODUCT_SPEC.md` とは別文書として扱います。

テスト用 SSH 鍵は `id_rsa` を使用します。

Computer Use API と Pico HID 経路を使う最小 E2E テストは `scripts/ps1/test_e2e_suite.ps1 -Case stage01_scenario01_open_browser` から実行します。Pi 5 側の API キーは `/home/nama/openai-api-key.txt` から読みます。

開発ステップ別の回帰テストは `scripts/ps1/test_e2e_suite.ps1` から実行します。

すべての実行可能な E2E ケースは、開始前に対象 PC の既存ウィンドウを閉じます。ランナーは `KEY ALT+F4` と、保存確認などで「いいえ」を選ぶための `KEY N` を複数回送ってから最初のスクリーンキャプチャへ進みます。

対象 PC へ入力する E2E の指示、検索語、テキスト本文は ASCII の英語にします。Pico の HID キーボード入力では日本語 IME を前提にしません。

### Codex / TDD 運用注意

このプロジェクトの TDD では、赤いテストを確認するときも、Codex が動いている Windows 環境だけで完結するとは限りません。`pi/` や `tests/` の変更は Pi 5 へコピーしてから実行するテストがあり、Hardware E2E は Pi 5、HDMI capture、OpenAI API、Pico UART、対象 PC を実際に使います。

TDD の赤/緑は、原則として以下の順に狭い層から確認します。

```text
1. ローカル unit test または対象ファイル単位の pytest
2. `--call-only` によるテスト呼び出し、ケース定義、Pi5 コマンド構築の確認
3. `--run-pi-integration` を付けた Pi5 統合テスト
4. preflight 成功後、`--run-hardware-e2e` を付けた Hardware E2E
```

Codex は Hardware E2E や Pi5 統合テストを、明示フラグなしの通常テストとして扱いません。実機テストを実行する前に、対象 PC を操作してよいこと、画面に秘密情報がないこと、Pi5 / Pico / capture の前提が揃っていることを確認します。実機テストの失敗は、まず `result.json`、`preflight.json`、スクリーンキャプチャ、remote command log を見て、実装ミスか `pi_ssh` / `pico_uart` / `capture_board` / `target_pc_state` / `openai_api` などの環境差分かを切り分けます。

## 実装時の基本姿勢

各ステップでは、必要最小限の差分だけを作ります。

望ましい進め方:

```text
1. 現在ステップの目的を確認する
2. README.md / AGENT.md / docs/PRODUCT_SPEC.md を読む
3. 必要なファイルだけ編集する
4. Pico firmware 変更がある場合だけビルドする
5. 実機確認方法を提示する
6. 人間の確認結果を待つ
```

実機確認が終わるまで、次の機能の実装には進みません。

## 禁止事項

```text
- 本開発仕様を一括実装する
- Keyboard / Mouse / UART / HDMI Capture / WebUI / Discord / email / Agent を一括変更する
- まだ確認していないハードウェア経路に依存したコードを書く
- 対象 PC に専用ソフトウェアをインストールする前提にする
- Pi 5 から対象 PC を直接 USB gadget として操作する設計に戻す
- Pico と Pi 5 を USB だけで同時制御できる前提にする
- 秘密情報をリポジトリに保存する
- WebUI を認証やバインド設定なしで外部公開する
- Discord bot token や SMTP password を設定ファイルへ直書きする
- samples/ を直接改造する
- README.md に開発手順や内部実装順を戻す
```

## 安全方針

安全機能の中心:

```text
- 非常停止
- 操作ログ
- スクリーンキャプチャログ
- LLM リスク判定
- ルールベース強制承認
- 承認待ち状態
- サスペンド / レジューム
- トークン予算
- 通知レート制限
```

LLM の判断だけに依存しません。ファイル削除、送信、購入、認証、設定変更、長時間操作などは、ルールベースでも承認必須にします。

## OpenAI API 方針

API キーは環境変数から読みます。

```text
OPENAI_API_KEY
OPENAI_MODEL
```

秘密情報をリポジトリに保存しません。

OpenAI API を使う機能:

```text
- Computer Use による画面理解と操作提案
- 複雑な指示の操作プランニング
- 操作リスク判定
- Discord チャット入力のコマンド変換
- 長時間プランの要約と進捗説明
```

## 推奨実装順

```text
Stage 1: Core分離
Stage 2: SQLite操作ログ
Stage 3: 非常停止と状態管理
Stage 4: WebUI拡張
Stage 5: プランニング
Stage 6: 承認フロー
Stage 7: メール通知
Stage 8: 長時間操作
Stage 9: トークン管理
Stage 10: Discord操作
```

詳細は `docs/PRODUCT_SPEC.md` の「推奨実装順」を参照します。

## 仕様未確定項目の扱い

`docs/PRODUCT_SPEC.md` の「要確認事項」に、ユーザー確認が必要な項目を集約します。仕様が確定したら、該当する要求仕様または詳細仕様へ反映し、要確認事項から削除します。
