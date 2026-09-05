# テスト環境メモ

この文書は、Raspberry Pi 5 実機を使ったテスト手順と接続情報をまとめる。

## 接続先

```text
host: 192.168.11.6
user: nama
key:  id_rsa
```

SSH と scp は `id_rsa` を使う。

疎通確認:

```powershell
ssh.exe -i id_rsa -l nama 192.168.11.6 hostname
```

期待結果:

```text
RaspberryPi
```

## PowerShell test scripts

Windows 側の PowerShell ラッパーは `scripts/ps1/` に集約する。

```powershell
.\scripts\ps1\test_unit.ps1
.\scripts\ps1\test_integration.ps1 -CallOnly
.\scripts\ps1\test_pytest_call_only_on_pi.ps1 -PytestArgs @('tests/unit','-q')
.\scripts\ps1\test_e2e_suite.ps1 -Stage stage01_core_io
```

削除済みの旧スクリプト:

```text
test_prepare.ps1      app.py を前面起動して戻らない旧確認用
test_test.ps1         test_prepare.ps1 の短縮版
test_open_browser.ps1 個別 E2E wrapper。現在は scripts/ps1/test_e2e_suite.ps1 -Case stage01_scenario01_open_browser を使う
```

## 最小API確認

Pi 5 上で `app.py` をテスト用ポートに起動し、Windows 側から `/api/status` を確認する。

Pi 5 上で起動:

```powershell
ssh.exe -i id_rsa -l nama 192.168.11.6 "cd /home/nama/pi; python3 app.py --host 192.168.11.6 --port 18080"
```

Windows 側から確認:

```powershell
Invoke-WebRequest -UseBasicParsing -Uri http://192.168.11.6:18080/api/status -TimeoutSec 10
```

確認済みの最小応答:

```text
bind_host: 192.168.11.6
bind_port: 18080
emergency_stopped: false
planning_enabled: false
suspended: false
system_logs: webui started
```

## 依存関係

Pi 5 側で Flask が未インストールの場合は、以下を実行する。

```powershell
ssh.exe -i id_rsa -l nama 192.168.11.6 "cd /home/nama/pi; pip3 install --break-system-packages -r requirements.txt"
```

確認済み:

```text
Python 3.13.5
Flask 3.1.3
```

## テスト時の注意

`killall python3` は他の Python プロセスも停止するため、Pi 5 上で別の Python 処理を動かしている場合は使わない。

LAN 限定アクセスの確認では、`--host 192.168.11.6` を指定して起動し、Windows 側から `http://192.168.11.6:<port>/api/status` を叩く。

HDMI キャプチャーや UART 実機経路を使わない最小確認では、まず `/api/status` を確認する。`/api/screenshot` はキャプチャーデバイスに依存する。`/api/command` は Request 入力として Computer Use API、HDMI capture、Pico UART、対象 PC 状態に依存する。低レベル HID を直接確認する場合は `/api/manual-hid` または `hid_client.py` を使う。

HDMI キャプチャーが成功しても `mean_brightness=0.0` の黒画面になる場合は、キャプチャーボードの安定待ちが足りない可能性が高い。Pi5 実機では `--warmup-frames 60` で非黒画面を取得できたため、capture-only、preflight、E2E の既定 warmup は 60 frames とする。

WebUI E2E はテスト用に Flask app を同一プロセス内で起動する。Pi5 上で手動確認用の `python3 app.py` が既に動いていると `/dev/video0` を掴んだままになり、テスト用 app が capture device を開けない。E2E runner は開始前に既存の `python3 app.py` を検出し、見つかった場合は失敗として止める。

## Computer Use + Pico E2E確認

`scripts/ps1/test_e2e_suite.ps1 -Case stage01_scenario01_open_browser` は、Pi 5 上でスクリーンキャプチャ、Computer Use API、Pico への HID 送信、再キャプチャ、ブラウザ表示判定までを確認する。

注意: このテストは接続PCのスクリーンキャプチャを OpenAI API に送信し、返された操作を Pico 経由で実機PCへ送る。実行前に、画面に秘密情報が表示されていないこと、対象PCを操作してよい状態であることを確認する。

すべての E2E ケースは、テスト開始前に対象 PC のウィンドウを閉じる前処理を行う。既定では `KEY ALT+F4` を送ったあと、保存確認ダイアログなどを閉じるために `KEY N` を送り、この組み合わせを複数回繰り返す。

```text
既定回数: 8
既定間隔: 0.5秒
```

必要な場合は以下の CLI 引数で調整する。

```text
--pre-test-close-attempts <回数>
--pre-test-close-delay <秒>
```

```powershell
.\scripts\ps1\test_e2e_suite.ps1 -Case stage01_scenario01_open_browser
```

WebUI の `Request` タブから `/api/command` に入る経路を個別に確認する場合は、Pi 5 に `pi/` を同期したあと、Pi 5 上で以下を実行する。この確認も Computer Use API、HDMI capture、Pico UART、対象 PC 状態に依存する。`Manual HID` タブや `/api/manual-hid` は低レベル HID のデバッグ用であり、通常の `Request` 指示とは分けて扱う。

```powershell
ssh.exe -i id_rsa -l nama 192.168.11.6 "cd /home/nama/pi; python3 webui_request_smoke.py open browser"
```

Pi 5 側の API キーは、以下のファイルから読む。

```text
/home/nama/openai-api-key.txt
```

実行する手順:

```text
1. テスト開始前に ALT+F4 と N を複数回送り、対象 PC のウィンドウを閉じる
2. スクリーンキャプチャを撮り、Computer Use API に "Open Browser" を依頼する。既にブラウザが表示されている場合は、HID 経路確認のため安全な `ESC` キー操作を返すよう指示する
3. Computer Use API の結果を、現在の Pico firmware が扱える HID コマンドとして送る
4. 再びスクリーンキャプチャを撮る
5. 新しいスクリーンキャプチャを Computer Use API に渡し、ブラウザが表示されているか True / False で判定する
6. True なら OK
```

現在の Pico firmware が扱える主な操作は `TEXT`、`KEY <key>`、`KEY WIN+R` のような修飾キー付きショートカット、`wait` 相当。Pi 5 側の E2E ランナーは、Computer Use API が返した `type`、`keypress`、`wait` を現在の HID コマンドへ変換して Pico に送る。Computer Use API がクリック、絶対座標移動など未対応の操作を返した場合、このテストは未対応アクションとして失敗する。

対象 PC へ入力されるテスト指示、検索語、テキスト本文は ASCII の英語にする。Pico が HID キーボードをエミュレートするため、日本語 IME 入力を前提にした E2E シナリオは作らない。

テスト成果物は Pi 5 側の以下に保存される。

```text
/home/nama/pi/captures/stage01_scenario01_open_browser_<timestamp>/
```

CLI 互換のため `open_browser_e2e` でも実行できるが、正式ケース名は `stage01_scenario01_open_browser`。

各成果物ディレクトリには、ステップごとのスクリーンキャプチャと `result.txt` が保存される。成果物名は以下の形式。

```text
step01_<step_name>_before.png
step01_<step_name>_after.png
result.txt
```

スクリーンキャプチャを Windows 側へ持ち帰る場合も、プロジェクトのルート直下には置かない。通常の調査 artifact は `captures/` に置く。ナレッジとして長期保存する代表画像だけを `docs/knowledge/screenshots/<stage>/` に移し、対応する説明を `docs/KNOWLEDGE.md` または `docs/knowledge/screenshots/README.md` に書く。

## ログDBの保存場所とリセット

通常の WebUI / `app.py` 実行時のログDBは、Pi5 上の以下に保存される。

```text
/home/nama/pi/runtime/app.db
/home/nama/pi/runtime/app.db-wal
/home/nama/pi/runtime/app.db-shm
```

E2E や統合テストでは、ケースごとの runtime 配下や `runtime/test/` 配下に別の `app.db*` が作られる。ログDBをリセットするときは、先に `python3 app.py` が動いていないことを確認する。起動中に削除すると SQLite の WAL/SHM とキャプチャ保持状態が残り、次のテストの切り分けを難しくする。

```powershell
ssh.exe -i id_rsa -l nama 192.168.11.6 "ps -eo pid=,args= | grep 'python3 app.py' | grep -v grep || true"
```

通常の WebUI ログDBだけを削除する場合:

```powershell
ssh.exe -i id_rsa -l nama 192.168.11.6 "cd /home/nama/pi; rm -f runtime/app.db runtime/app.db-wal runtime/app.db-shm"
```

テスト用DBも含めて `runtime/` 配下のログDBをすべてリセットする場合:

```powershell
ssh.exe -i id_rsa -l nama 192.168.11.6 "cd /home/nama/pi; find runtime -name 'app.db*' -type f -delete"
```

この操作はSQLiteログDBだけを消す。スクリーンショットを消す場合は別途 `runtime/screenshots/` や E2E artifact を確認してから削除する。

## 開発ステップ別E2Eスイート

開発ステップ別のテストシナリオは `docs/TEST_SCENARIOS.md` にまとめる。ケース定義の実体は `pi/pico_hid_bridge/e2e/cases.py`、まとめ実行 CLI の実体は `pi/tools/run_e2e_suite.py` に置く。`pi/e2e_cases.py` と `pi/run_e2e_suite.py` は既存コマンド互換の入口として残す。

TDD 用のテスト実装計画は `docs/TEST_IMPLEMENTATION_PLAN.md`、テストプログラムの関数名、引数、実行条件、失敗時の切り分けは `docs/TEST_PROGRAM_SPEC.md` にまとめる。

Stage01 実装中に分かった実機固有の問題、失敗した試み、最終解は `docs/KNOWLEDGE.md` にまとめる。Pico firmware、JISキーボード配列、UART ACK、長文TEXT chunk、Paintでのファイルオープン手順を変更する前に参照する。

## pytest テストプログラム

pytest ベースのテストは `tests/` に置く。フル E2E 実行と、テスト呼び出しのみの確認を同じテスト関数で扱う。

```text
tests/unit/         ローカルで実行できるユニットテスト
tests/integration/  Pi5、WebUI、ログ、通知系の統合テスト
tests/preflight/    Hardware E2E 前提条件チェック
tests/e2e/          開発ステップ別 E2E シナリオ 84 件
tests/helpers/      TestEnvironment、SSH、artifact、E2E runner helper
```

テスト呼び出しのみを確認する場合は `--call-only` を付ける。このモードでは、対象PC操作、OpenAI API呼び出し、Pico UART送信、キャプチャ取得を実行せず、テスト関数、シナリオ名、Pi5コマンド構築、expected_failure 判定だけを確認する。

## TDD 開発時の実行順序

このプロジェクトの TDD では、Codex が動いている Windows 側だけで完結するテストと、Pi5 / Pico / HDMI capture / 対象 PC / OpenAI API を使うテストを明確に分ける。赤いテストを作る場合も、最初から Hardware E2E を実行するのではなく、実装対象に応じて最も狭い層から確認する。

```text
1. ローカル unit test:
   ハードウェア不要の関数、設定、変換、判定ロジックを確認する。

2. call-only:
   対象 PC 操作、OpenAI API、Pico UART、capture を使わず、pytest 関数、シナリオ名、Pi5 コマンド構築、expected_failure 判定を確認する。

3. Pi5 integration:
   `--run-pi-integration` を明示して、Pi5 上のファイル、依存関係、WebUI、ログ、通知系を確認する。原則として対象 PC は操作しない。

4. Hardware E2E:
   preflight が成功し、対象 PC を操作してよい状態で、`--run-hardware-e2e` を明示して実行する。
```

`pi/` や `tests/` を変更した場合、Pi5 上で実行する赤/緑確認では、対象ファイルが `/home/nama/pi` に同期されていることもテスト前提に含める。ローカル unit test が緑でも、Pi5 統合または Hardware E2E の対象機能を変更した場合は、該当するリモート実行まで通して初めて実機経路の緑とみなす。

Hardware E2E の失敗は、すぐ実装ミスと断定しない。`result.json`、`preflight.json`、`remote_commands.jsonl`、`hid_commands.jsonl`、`step*_before.png`、`step*_after.png` を見て、`implementation` と `pi_ssh` / `pi_dependency` / `pico_uart` / `capture_board` / `target_pc_state` / `openai_api` などの環境差分を切り分ける。

Windows 側からの代表コマンド:

```powershell
.\scripts\ps1\test_all.ps1 -CallOnly
.\scripts\ps1\test_e2e_pytest.ps1 -CallOnly -Stage stage01_core_io
.\scripts\ps1\test_e2e_pytest.ps1 -CallOnly -Case stage01_scenario01_open_browser
```

Pi5 側でテスト呼び出しのみを確認する場合:

```powershell
.\scripts\ps1\test_pytest_call_only_on_pi.ps1
```

このスクリプトは `pi/` を `/home/nama/pi` に同期し、`tests/`、`pytest.ini`、`config/` を `/home/nama/pi` に配置してから、Pi5 上で以下を実行する。

```bash
cd /home/nama/pi
python3 -m pytest tests --call-only
```

フル E2E を実行する場合は、明示的に `--run-hardware-e2e` を付ける。

```powershell
.\scripts\ps1\test_e2e_pytest.ps1 -RunHardwareE2E -Stage stage01_core_io
```

Pi5 統合テストを実環境に対して実行する場合は、明示的に `--run-pi-integration` を付ける。

```powershell
.\scripts\ps1\test_integration.ps1 -RunPiIntegration
```

依存関係:

```bash
cd /home/nama/pi
pip3 install --break-system-packages -r requirements.txt
```

2026-07-03 時点の確認結果:

```text
Pi5 /home/nama/pi:
python3 -m pytest tests --call-only -q
133 passed

python3 -m pytest tests/e2e --call-only --e2e-stage stage01_core_io -q
7 passed, 70 skipped
```

2026-07-04 時点の Stage02 確認結果:

```text
Pi5 /home/nama/pi:
python3 -m pytest tests/integration/test_operation_log.py --run-pi-integration -q
6 passed

python3 -m pytest tests/e2e --call-only --e2e-stage stage02_operation_log -q
84 passed, 70 skipped

Windows 側:
.\scripts\ps1\test_e2e_suite.ps1 -Stage stage02_operation_log
Scenario1-6: RESULT OK
Scenario7: RESULT EXPECTED FAILURE
```

2026-07-04 時点の step13 / ACK timeout 回帰確認結果:

```text
Pico firmware:
  pico/build/step13.uf2
  PING command added for UART recovery probe

Pi5 smoke:
  cd /home/nama/pi; python3 hid_client.py PING --port /dev/serial0 --timeout 0.5
  sent: PING

Pi5 unit / call-only:
  tests/unit/test_hid_commands.py includes ACK timeout coverage
  tests/integration/test_pi_environment.py uses PING for pico_uart_smoke
  157 passed

Pi5 integration:
  python3 -m pytest tests/integration/test_pi_environment.py::test_pi_pico_uart_smoke --run-pi-integration -q
  1 passed

Stage01 regression:
  python3 -m pytest tests/e2e --call-only --e2e-stage stage01_core_io -q
  87 passed, 70 skipped
  .\scripts\ps1\test_e2e_suite.ps1 -Stage stage01_core_io
  Scenario1-5: RESULT OK
  Scenario6-7: RESULT EXPECTED FAILURE

Stage02 degradation check:
  python3 -m pytest tests/e2e --call-only --e2e-stage stage02_operation_log -q
  87 passed, 70 skipped
  .\scripts\ps1\test_e2e_suite.ps1 -Stage stage02_operation_log
  Scenario1-6: RESULT OK
  Scenario7: RESULT EXPECTED FAILURE
```

一覧表示:

```powershell
.\scripts\ps1\test_e2e_suite.ps1 -List
```

実装済みケースだけを回帰実行:

```powershell
.\scripts\ps1\test_e2e_suite.ps1
```

特定ステージだけを実行:

```powershell
.\scripts\ps1\test_e2e_suite.ps1 -Stage stage01_core_io
```

未実装ステージを TDD の赤として実行する場合:

```powershell
.\scripts\ps1\test_e2e_suite.ps1 -Case stage05_scenario02_google_http_status_codes
```

`pending` のケースは、通常の回帰実行ではスキップされる。新しい開発ステージへ入るときに `--include-pending` を付けて実行し、失敗することを確認してから実装を始める。

メール送信機能の E2E では、Pi 5 側の SMTP アカウント情報を以下から読み、宛先判定に使う。外部メール送信は行わず、Stage07 E2Eランナーは `[email].delivery = "console"` に切り替えて送信内容をコンソールへ出力する。

```text
/home/nama/mail-send-vert.txt
```

## E2Eテスト追加方法

E2Eテストの共通処理は `pi/pico_hid_bridge/e2e/runner.py` に置く。個別ケースは `pi/pico_hid_bridge/e2e/cases.py` に `E2ETestCase` として追加する。`pi/e2e_hid_runner.py` と `pi/e2e_cases.py` は既存手順互換の薄いimportラッパーとして残す。

低レベル処理は `pi/pico_hid_bridge/` に分離している。

```text
pico_hid_bridge/capture.py       スクリーンキャプチャ
pico_hid_bridge/computer_use.py  Computer Use API
pico_hid_bridge/hid.py           Pico UART HIDコマンド
pico_hid_bridge/actions.py       action実行とイベント通知
pico_hid_bridge/notifications.py email / Discord 連携の追加場所
pico_hid_bridge/web/             Flask WebUI とHTML/CSS/JavaScript
pico_hid_bridge/cli/             CLI実装
pico_hid_bridge/e2e/             E2Eケース定義とランナー
```

Computer Use API へ渡す共通プロンプトは `pico_hid_bridge/computer_use.py` の既定値、または `config/local.toml` の `[openai].computer_prompt` で決まる。既定では keyboard-first とし、アプリ起動は `WIN+R`、アクティブアプリ切り替えは `ALT+TAB` を優先する。`controller.py` で個別に確認するときは `--config config/local.toml` または `--computer-prompt` で同じ方針を明示できる。

新しいケースで定義する主な項目:

```text
name             成果物ディレクトリ名とCLI指定名
stage            開発ステージ名
description      ケースの目的
implemented      実行可能なら true、TDD ひな形なら false
pending_reason   未実装理由
requires         実行に必要な外部条件
steps            E2EStep の列
action_task      スクリーンキャプチャを渡して PC操作を得る指示
verify_task      操作後スクリーンキャプチャを渡して True / False で判定する指示
success_message  True のときの表示
failure_message  False のときの表示
```

実行形式:

```powershell
ssh.exe -i id_rsa -l nama 192.168.11.6 "cd /home/nama/pi; python3 run_e2e_case.py open_browser_e2e --api-key-file /home/nama/openai-api-key.txt"
```

メール通知や Discord 通知をテスト途中に追加する場合は、`pico_hid_bridge.notifications` に `EventSink` 実装を追加し、`pico_hid_bridge.actions.ActionExecutor` に渡す。
