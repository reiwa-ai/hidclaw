# Stage01 実装ナレッジ

この文書は、Stage01 Core I/O を実装したときの試行錯誤を残すための作業記録です。次のステージで同じ問題を再調査しなくて済むように、成功した方法だけでなく、失敗した仮説や途中で捨てた方針も保存します。

## 最終状態

Stage01 は 2026-07-04 に Pi5 実機 E2E で全シナリオを確認しました。

```text
Pi5 call-only:
  tests/e2e --e2e-stage stage01_core_io -q
  76 passed, 70 skipped

Pi5 unit:
  tests/unit -q
  38 passed

Hardware E2E:
  .\scripts\ps1\test_e2e_suite.ps1 -Stage stage01_core_io
  Scenario1-5: RESULT OK
  Scenario6-7: RESULT EXPECTED FAILURE
```

Stage01 の完成条件は、Windows 上のローカルテストだけでは満たしません。Pi5 へソースをコピーし、Pi5 上で pytest または E2E runner を動かし、HDMI capture、OpenAI Computer Use API、Pico UART、対象 PC の USB HID 入力まで含む実機 E2E を通して初めて緑とします。

## 実機テスト経路

Pi5 接続情報は以下です。

```text
host: 192.168.11.6
user: nama
key:  id_rsa
remote source: /home/nama/pi
OpenAI API key file: /home/nama/openai-api-key.txt
UART: /dev/serial0
capture: /dev/video0
```

代表コマンド:

```powershell
.\scripts\ps1\test_pytest_call_only_on_pi.ps1 -PytestArgs @('tests/e2e','--e2e-stage','stage01_core_io','-q')
.\scripts\ps1\test_e2e_suite.ps1 -Stage stage01_core_io
```

call-only は、テスト関数、シナリオ定義、フィルタ、Pi5 へのコピーを確認する早いゲートです。ただし対象 PC 操作、OpenAI API、Pico UART、HDMI capture を使わないため、Stage01 完了判定には使えません。

## Capture warmup

初期の capture-only / E2E では、`mean_brightness=0.0` の黒画面が出ました。これは対象 PC が黒いというより、USB HDMI capture の安定待ち不足でした。

試したこと:

```text
- capture直後のフレームをそのまま使う
- min_brightness だけで判定する
```

問題:

```text
- デバイスが安定する前のフレームを拾うと黒画面になり、E2E の画面判定が不安定になる
```

最終解:

```text
--warmup-frames 60
```

`controller.py`、preflight、E2E runner の既定は 60 frames を前提にします。黒画面が再発した場合は、まず HDMI 配線や対象 PC 状態を見る前に warmup frames と capture artifact を確認します。

## Pico からキー入力が届かない問題

症状:

```text
Pico から対象 PC へキー入力が送られていないように見える。
以前は動いており、Pico firmware は変えていないという前提だった。
```

最初に疑ったこと:

```text
- Pi 側 controller.py または action mapping の変更
- Pico UART 配線
- 対象 PC 側 focus
```

切り分け:

```text
python3 hid_client.py KEY ESC
python3 hid_client.py KEY WIN
python3 hid_client.py KEY WIN+R
```

分かったこと:

```text
- 短いキー入力は届く
- WIN 単独キーが扱えないと、スタートメニューや一部の Computer Use 返却操作が実行できない
```

最終解:

```text
- Pico firmware で修飾キー単独の KEY を許可する
- Pi 側 validate_command / normalize_keypress でも standalone modifier を許可する
- 修飾キー単独は通常キーより長く押す
```

Pico 側では `KEY WIN` のように key code 0、modifier だけの HID report を送る。短すぎる押下は Windows に無視されやすいため、modifier-only は通常キーより長い press duration にしています。

## JIS キーボード配列問題

症状:

```text
Paint で画像を開くパス入力が壊れた。
例:
  mspaint c+]Users]user]PictuKEY ENTER

Calculator の 123+456 が 123:456 のようにずれる。
Windows パスの backslash が消える、または別記号として入る。
```

原因:

```text
対象 PC は日本語キーボード配列として Pico HID keyboard を解釈していた。
Pico の ASCII -> HID usage 変換は US 配列寄りだった。
```

失敗した試み:

```text
- シナリオ側で slash など別文字に逃がす
- mspaint の Run 引数で直接画像を開く
- 送信テキストを短くして配列問題を回避する
```

失敗理由:

```text
- Windows のファイルパスでは backslash を安定して送る必要がある
- シナリオの目的は Paint の Open dialog 経路を確認することだった
- 記号を避けると、実際に必要な HID 文字入力の保証にならない
```

最終解:

```text
- Pico 側の ASCII -> HID usage 変換を日本語配列向けに補正する
- backslash は JIS Yen key usage を使う
- underscore / pipe など JIS 固有 usage が必要な文字は report descriptor の usage/logical max を拡張する
```

実装上の注意:

```text
HID_KEY_JIS_RO  = 0x87
HID_KEY_JIS_YEN = 0x89
```

標準の keyboard report descriptor の範囲だけでは JIS 固有 usage を送れないため、Pico firmware では `HID_JIS_KEYBOARD_REPORT_DESC()` を定義し、logical max / usage max を `0x89` まで広げました。

確認方法:

```text
1. Notepad を開く
2. A\B C:\Users\user\Pictures\test.png Z を入力する
3. 見た目が yen 記号でも、Windows パスとして機能することを dir で確認する
4. cmd で dir C:\Users\user\Pictures\test.png が成功することを確認する
```

日本語 Windows では backslash が yen 記号に見えることがあります。表示だけで失敗と判断せず、`dir` でパス解決を確認します。

## 長文送信と KEY ENTER 混入

症状:

```text
長い TEXT の直後に KEY ENTER を送ると、対象 PC 側に次のように混ざる。
  ...PictuKEY ENTER

また、長文送信後に Notepad に何も表示されず、次の短文テストを始めた瞬間に前の長文が一気に入力されることがあった。
```

原因候補:

```text
- Pi から Pico へ UART 行を送るペースが速すぎる
- Pico が HID 入力を完了する前に次の UART コマンドを受ける
- Pi 側は write/flush 完了を「対象 PC への入力完了」と誤解していた
- Pico 側に処理完了 ACK がなかった
```

失敗した試み:

```text
- Pi 側で特殊キー前に固定 sleep を入れる
- Pico 側の最大 TEXT 長だけを 256 へ伸ばす
- ACK なしのまま UART timeout を伸ばす
```

失敗理由:

```text
- 固定 sleep は対象 PC や文字数で必要時間が変わる
- 最大 TEXT 長を伸ばしても、Pico が処理中であることを Pi 側が分からない
- timeout を伸ばすだけでは送信順序の同期にならない
```

最終解:

```text
- Pico は各 UART コマンド処理完了後に PICO_HID_OK または PICO_HID_ERR を返す
- Pi 側 send_line は ACK を待ってから次の UART 行を送る
- 長い TEXT は Pi 側で 20 文字ずつ複数の TEXT 行へ分割する
- TEXT の ACK timeout は文字数に応じて長くする
```

現在の仕様:

```text
Pico UART 1行: TEXT prefix + 最大256文字 + newline
Pi 側 TEXT 送信: 20文字ごとに chunk
Pi 側: 各 chunk の PICO_HID_OK を待つ
Pico 側: HID入力完了後に ACK を返す
```

この方式により、長文の末尾に `KEY ENTER` が混ざる問題と、長文が後続テストのタイミングで遅れて入力される問題を避けています。

## Scenario5 の仕様変更履歴

Stage01-Scenario5 は、途中で仕様が何度か変わりました。

初期案:

```text
Paint を開いて C:\Users\user\Pictures.png を読み込む
```

問題:

```text
- 正しいファイルパスではなかった
- mspaint の引数でファイルを開く流れになっていた
```

修正1:

```text
C:\Users\user\Pictures\test.png に変更
```

修正2:

```text
mspaint <path> ではなく、空の Paint を開いてメニューの File -> Open から開く
```

問題:

```text
Computer Use がメニュー操作で不安定になりやすい。
ファイルメニューの位置や UI 状態に依存する。
```

最終解:

```text
1. WIN+R で mspaint を起動する
2. 空の Paint が開いていることを確認する
3. CTRL+O で Open dialog を出す
4. C:\Users\user\Pictures\test.png を入力して ENTER
5. 画像が表示されたことを確認する
6. 画像内に "This is test" が見えることを確認する
```

テスト側の固定確認:

```text
tests/unit/test_e2e_case_definitions.py
  test_stage01_scenario05_loads_picture_file_and_verifies_text
```

このテストは、Scenario5 が `mspaint C:\Users\user\Pictures\test.png` に戻らないこと、`CTRL+O` を使うこと、対象パスが `C:\Users\user\Pictures\test.png` であることを固定しています。

## Expected failure ケース

Stage01 には失敗することが正しいケースがあります。

```text
stage01_scenario06_expected_failure_unsupported_drag
  Paint の freehand drag は現在の Pico firmware / action mapping では未対応。
  Computer Use が drag action を返し、それを unsupported として検出できれば成功。

stage01_scenario07_expected_failure_nonexistent_app
  DefinitelyNotARealApp12345 を開けないことを検出できれば成功。
```

注意点:

```text
expected_failure は環境エラーを成功扱いしない。
preflight 失敗、capture 黒画面、OpenAI API エラー、Pico UART 不通は infrastructure failure として扱う。
```

## テスト実行時の判断ルール

失敗したら、すぐ実装を直さずに以下を見ます。

```text
1. result.txt / result.json
2. preflight 結果
3. step*_before.png / step*_after.png
4. hid command log
5. OpenAI response
6. Pi5 SSH / UART / capture の状態
```

代表的な分類:

```text
SSHできない:
  pi_ssh

/dev/video0 がない、または黒画面:
  capture_board / target_pc_state

hid_client.py PING が失敗:
  pico_uart / firmware / wiring

HID は効くが文字が違う:
  Pico firmware の keyboard layout mapping

Computer Use が未対応 action を返す:
  action mapping 未対応、または expected_failure 対象

OpenAI API 401/403/429/5xx:
  openai_api
```

Pi5 上の実装問題なら直して TDD を続けます。Pi5、Pico、capture、対象 PC、OpenAI API など外部環境の問題なら、無理に production code を変えず、環境問題として止めて報告します。

## 成果物の扱い

Stage01 中には、多くのスクリーンショットと個別 E2E artifact を作りました。

例:

```text
step10_text_length_check*.png
step11_chunked_text_check.png
step12_backslash_notepad_check.png
step12_dir_test_png_check.png
stage01_scenario05_paint_text_<timestamp>/
```

これらは調査ログとして有用ですが、ソースコードではありません。必要な知識はこの文書に移し、PNG や captures は `.gitignore` で追跡対象外にします。再調査が必要な場合は、同じ手順で新しい artifact を作ります。

長期ナレッジとして残す必要がある代表スクリーンショットだけは、プロジェクトルート直下ではなく `docs/knowledge/screenshots/<stage>/` に置きます。Stage01 の代表画像は `docs/knowledge/screenshots/stage01/` に整理済みです。通常の E2E artifact や一時調査画像は `/home/nama/pi/captures/` またはローカルの `captures/` に置き、知見を文書化したら削除します。

## 今後のステージへの教訓

```text
- ローカル green と実機 green を混同しない
- E2E の prompt は ASCII English に保つ
- 文字入力の問題は Pi 側だけでなく Pico firmware と対象 OS 配列を見る
- 長文入力は必ず chunk + ACK で同期する
- Open dialog など UI 操作はメニュー座標よりキーボードショートカットを優先する
- 期待失敗ケースは「失敗したから成功」ではなく、期待した失敗信号を検出して成功にする
- テストスクリプトは終了コードを返し、TDD の赤/緑を曖昧にしない
```

# Stage02 実装ナレッジ

Stage02 Operation Log では、ユーザー入力、実際に送った HID 操作、スクリーンショット、失敗理由を Pi5 側の SQLite に永続化しました。2026-07-04 時点で Stage02 の全シナリオを Pi5 実機 E2E で確認済みです。

```text
Pi5 integration:
  tests/integration/test_operation_log.py --run-pi-integration -q
  6 passed

Pi5 call-only:
  tests/e2e --e2e-stage stage02_operation_log -q
  84 passed, 70 skipped

Hardware E2E:
  .\scripts\ps1\test_e2e_suite.ps1 -Stage stage02_operation_log
  Scenario1-6: RESULT OK
  Scenario7: RESULT EXPECTED FAILURE

Stage01 regression:
  .\scripts\ps1\test_e2e_suite.ps1 -Stage stage01_core_io
  Scenario1-5: RESULT OK
  Scenario6-7: RESULT EXPECTED FAILURE
```

## SQLite ログの設計判断

最初の赤:

```text
- pico_hid_bridge.operation_log が存在しない
- WebUI /api/command の実行後に SQLite 行が残らない
- Stage02 の E2E ケースが pending のまま
```

最終解:

```text
- OperationLogStore を追加し、user_input_log / operation_log / screenshot_log / error_log を作成する
- WebUI の append_log と /api/screenshot から SQLite へも記録する
- E2E runner では artifact ごとに runtime/app.db を作る
- HID action の送信結果は EventSink で operation_log へ記録する
```

E2E の SQLite DB は本番用 `runtime/app.db` を直接使わず、各 artifact 配下に作ります。これにより、ケースごとの検証、壊れた DB の fixture、スクリーンショットローテーションを他ケースへ漏らさずに実行できます。

## スクリーンショット保持上限

Stage02-Scenario4 は「ディスクを実際に大量消費する」テストにしない。テスト用の小さい `max_screenshots` を使い、古い `screenshot_log` 行と対応ファイルが削除されることを確認します。

失敗しやすい方針:

```text
- 最大容量まで巨大ファイルを作る
- OS の空き容量に依存して判定する
- 画像ファイルだけ削除し、SQLite 行を残す
```

最終解:

```text
- max_screenshots=2 の fixture を作る
- 3件以上の screenshot_log を記録する
- 最古の DB 行とファイルが両方消えることを見る
```

将来 `max_storage_mb` を厳密に実装する場合も、Stage02 の安定回帰ではまず小さい fixture を使い、実ディスク容量に依存しないテストにします。

## 壊れた DB の扱い

Stage02-Scenario7 は、壊れた SQLite DB を安全に検出して復旧する期待失敗ケースです。ここでの成功は「何も起きなかったこと」ではなく、壊れた DB を `.corrupt-<timestamp>` に退避して新しい DB を作り、`recovery_performed=True` を観測できることです。

注意:

```text
- 壊れた DB を黙って削除しない
- 復旧後もログ書き込みを続行できることを確認する
- E2E の結果表示は EXPECTED FAILURE だが、これは fault injection を検出した成功を意味する
```

## Computer Use の verify prompt

Stage02 中に、確認ステップで Computer Use が `SHIFT` などの操作を返したことがありました。verify step は画面判定だけを求める必要があります。

安定した指示:

```text
Do not control the computer. Do not request keypress, click, or any other action.
Return exactly 'True' if ...; otherwise return exactly 'False'.
```

この文を省くと、verify のつもりが Pico への追加 HID 操作になり、ログや対象 PC 状態が余計に変わります。Stage02 以降の verify prompt では、操作禁止と True/False のみを明示します。

## 余計な UI 操作を避ける

Stage02-Scenario3 では、スクリーンショットログを作るだけのケースで Computer Use が `double_click` を返し、未対応 action または Pico timeout につながりました。ログや保存上限を検証するケースでは、対象 PC の複雑な UI 操作を目的にしない。

最終解:

```text
- スクリーンショット前後を作りたいだけなら ESC + wait など無害な操作にする
- ログの中身は SQLite を直接検証する
- 画面認識は「読める状態か」の補助確認に留める
```

追加対策:

```text
- Pico firmware に PING を追加する
- PING は対象 PC へ HID 入力を送らず、PICO_HID_OK だけを返す
- ACK timeout 後の復帰確認では、KEY ESC より先に PING を使う
```

## 統合テストの実行場所

`tests/integration/test_operation_log.py` は、Codex ホストから呼ばれる場合と Pi5 上で直接実行される場合の両方があります。Pi5 上の `/home/nama/pi` で実行中なら SSH で自分自身へ戻らず、ローカル `python3 -c` probe として走らせます。

この判断を入れておくと、`scripts/ps1/test_pytest_call_only_on_pi.ps1` や Pi5 直接実行で SSH の二重化に悩まされません。

## Stage02 final validation notes

Date: 2026-07-04

Stage02 is complete when both the Pi-side tests and the real hardware E2E pass. Do not judge Stage02 log scenarios only by visual Computer Use verification; the SQLite records are the source of truth.

Final checks added during completion:

- Stage02-Scenario2 must contain a real HID operation in `operation_log`. A `WAIT` entry alone is not enough.
- Stage02-Scenario3 must contain both `before` and `after` rows in `screenshot_log`. Two screenshots with the same event are not enough.
- Stage02 E2E steps may defer visual success to `validate_stage02_logs()` after taking the required before/after captures.
- Keyboard and text HID commands have a short automatic settle delay so `WIN+R` followed by `chrome` does not lose the leading characters.

Commands used for the completion gate:

```powershell
.\scripts\ps1\test_pytest_call_only_on_pi.ps1 -PytestArgs @('tests/unit/test_e2e_hid_runner.py','tests/unit/test_e2e_case_definitions.py','tests/unit/test_operation_log.py','tests/unit/test_app_operation_log.py','tests/integration/test_operation_log.py','-q')
.\scripts\ps1\test_e2e_suite.ps1 -Stage stage02_operation_log
.\scripts\ps1\test_e2e_suite.ps1 -Stage stage01_core_io
```

## Stage03 and Stage04 completion notes

Date: 2026-07-04

Stage03 and Stage04 use a WebUI-oriented E2E path. The runner creates the Flask WebUI app on the Pi5 with an isolated runtime directory, calls WebUI APIs through `app.test_client()`, and uses `/api/command` for Request scenarios that must exercise Computer Use -> Pico UART -> target PC. This avoids making the target PC browser operate the WebUI itself while still testing the production WebUI API path.

Important decisions:

- Stage03 emergency stop blocks Manual HID. A new Request command clears emergency stop and starts fresh.
- Suspend blocks Manual HID until Resume clears the state.
- A small `/api/approval-test` fixture exists only to validate that Emergency Stop cancels pending approvals as `cancelled_by_emergency_stop`.
- WebUI now shows User Log, Operation Log, and System Log as separate panes.
- Manual HID rejects `KEY ALT`, `KEY CTRL`, and `KEY SHIFT` as standalone non-WIN modifiers. `KEY WIN` remains allowed because the Pico firmware supports the Windows key as a standalone key.
- WebUI Request blocks known unsupported/freehand mouse-drag requests and the `DefinitelyNotARealApp12345` failure fixture instead of reporting misleading success.
- `/api/command` continues Computer Use turns after executing actions, so multi-step WebUI Request cases can progress beyond the first HID batch.

Completion gate:

```powershell
.\scripts\ps1\test_pytest_call_only_on_pi.ps1 -PytestArgs @('tests/unit/test_e2e_hid_runner.py','tests/unit/test_e2e_case_definitions.py','tests/unit/test_app_operation_log.py','tests/unit/test_hid_commands.py','tests/unit/test_run_e2e_suite.py','-q')
.\scripts\ps1\test_e2e_suite.ps1 -Stage stage03_runtime_safety
.\scripts\ps1\test_e2e_suite.ps1 -Stage stage04_webui_control
.\scripts\ps1\test_e2e_suite.ps1 -Stage stage02_operation_log
.\scripts\ps1\test_e2e_suite.ps1 -Case stage01_scenario04_calculator_basic
```

## WebUI persistent capture service

Date: 2026-07-05

Problem observed:

- When WebUI JavaScript polling refreshed `/api/screenshot` while `/api/command` was running, Computer Use screenshot capture could fail with `failed to open capture device: /dev/video0`.
- `ffplay` and the initial WebUI screen were healthy, so the likely cause was not hardware or device ID. The risky flow was opening and closing `/dev/video0` for every capture request from multiple paths.
- Reopening the HDMI capture device can also make the target PC detect a display disconnect/reconnect, causing screen flash and requiring more warmup frames.

Final design:

- WebUI mode starts one `CaptureService` thread at app startup.
- The service opens `/dev/video0` once, continuously reads frames, and keeps the latest frame in memory.
- `/api/screenshot` and Computer Use screenshot responses both read from the same latest frame.
- Device open/close should happen only at WebUI app startup/shutdown. CLI capture-only paths may still use one-shot capture.
- WebUI E2E runner starts the service for WebUI cases and stops it after each case, so Stage03/Stage04 tests do not leave a capture handle open between cases.
- Before WebUI E2E starts, the runner checks whether `python3 app.py` is already running. A previously opened WebUI app can hold `/dev/video0` and make the test app fail to open the capture device.

Regression tests added:

- `tests/unit/test_capture_service.py` verifies that `CaptureService` opens `VideoCapture` once, serves updated frames, and releases the device on stop.
- `tests/unit/test_app_operation_log.py` verifies `/api/screenshot` uses the shared service and `/api/command` passes that service to Computer Use.

Validation commands:

```powershell
.\scripts\ps1\test_pytest_call_only_on_pi.ps1 -PytestArgs @('tests/unit','-q')
.\scripts\ps1\test_e2e_suite.ps1 -Case stage04_scenario01_lan_webui_status
.\scripts\ps1\test_e2e_suite.ps1 -Case stage04_scenario08_webui_request_open_browser
```

Additional live-server check:

- Started `python3 app.py --host 127.0.0.1 --port 18083` on the Pi5.
- Polled `/api/screenshot` every 0.5 seconds while posting `/api/command` with `open browser`.
- Result: command returned 200, all polling screenshots returned 200, and the final screenshot returned 200.

## WebUI operation/log split

Date: 2026-07-05

The WebUI top screen became crowded once user, operation, and system logs were all shown beside the capture and command controls. The UI is now split into two views:

- Operation view: capture screen, Request / Plan / Manual HID command modes, status, suspend/resume, and emergency stop.
- Logs view: Refresh and Date/Time search controls, User Log, Operation Log, detailed timeline, and a token usage bar graph.

Data flow:

- The Logs view reads from SQLite through `/api/logs/detail`.
- `system_log` stores persistent system events that used to be memory-only.
- `token_usage_log` stores per-Computer-Use response token usage. When OpenAI usage metadata is missing, the system records `system_log.event=token_usage/status=unknown` and an estimated token count instead of silently treating the usage as zero.
- The token graph is rendered locally with CSS/JavaScript bars instead of a CDN dependency so the Pi5 WebUI works in a closed LAN environment.
- User Log, Operation Log, the detailed timeline, and the token graph are all displayed newest-first.
- Token graph rows use the left-side log row timestamps. Each bar shows the total tokens consumed after the chronologically previous left-side log timestamp and up to the current left-side log timestamp.
- The Logs toolbar shows aggregate consumed tokens for all time and the current browser-local month. When From/To is set, it also shows the aggregate for that filtered range. These totals are queried from SQLite with `/api/tokens` instead of being summed from the 500 visible log rows.

Validation:

```powershell
.\scripts\ps1\test_pytest_call_only_on_pi.ps1 -PytestArgs @('tests/unit','-q')
.\scripts\ps1\test_e2e_suite.ps1 -Case stage04_scenario01_lan_webui_status
.\scripts\ps1\test_e2e_suite.ps1 -Case stage04_scenario03_planning_toggle
.\scripts\ps1\test_e2e_suite.ps1 -Case stage04_scenario04_log_panes
```

## Pi package layout refactor

Date: 2026-07-05

After Stage04 WebUI work, `pi/app.py` and the E2E files had grown into mixed entrypoint/implementation modules. The Pi side is now organized by feature under `pi/pico_hid_bridge/`:

- `pico_hid_bridge/web/`: Flask WebUI implementation and the HTML/CSS/JavaScript template.
- `pico_hid_bridge/cli/`: CLI implementations such as the Computer Use controller.
- `pico_hid_bridge/e2e/`: E2E model, case definitions, and runner implementation.
- `pi/tools/`: hardware-check and test helper command implementations.

The old `pi/app.py`, `pi/controller.py`, `pi/e2e_cases.py`, `pi/e2e_hid_runner.py`, `pi/run_e2e_case.py`, and `pi/run_e2e_suite.py` files remain as thin compatibility entrypoints/import wrappers. Add new implementation code to the feature packages, not to those wrappers.

## Stage05 planning wrapper

Date: 2026-07-05

Implementation intent:

- Stage05 adds planning without replacing the existing Computer Use flow.
- The new wrapper takes one user request, asks the OpenAI API for a JSON plan, then sends each returned step through the same `execute_computer_use_request` path used by normal Request mode.
- The planner must not emit low-level HID commands. Raw `KEY`, `TEXT`, `MOUSE_MOVE`, and `CLICK` commands remain Manual HID concerns.
- Keep the prompt generic. Do not tune it for a single E2E scenario; when behavior is poor, revise the generic planning prompt before changing execution code.

Prompt/API lessons:

- The planning request uses structured JSON output with a `pc_operation_plan` schema containing `risk_level`, `requires_approval`, `summary`, and `steps`.
- Each step is a natural-language instruction for the existing Computer Use executor, not an action list for Pico.
- The planner request enables reasoning effort so the model can think through multi-step decomposition before emitting the JSON result.
- The prompt strongly prefers keyboard-friendly Windows workflows, including `WIN+R` for opening applications and `ALT+TAB` for switching active windows.
- The Computer Use prompt must name unsupported HID choices explicitly. Stage05 exposed `PAGEDOWN` and `drag` actions, so the prompt now lists supported keys and says not to use page navigation keys or drag.
- Computer Use may answer a research/summarize step with natural language instead of controlling the PC. The WebUI execution path retries once with a stronger instruction to use computer tool actions and type the summary into the physical PC.
- Computer Use may emit long or multiline `type` actions for summaries. `ActionExecutor` splits multiline text into `TEXT` plus `KEY ENTER`, and splits long text into 256-character `TEXT` lines before the lower UART layer chunks each line into 20-character Pico batches.
- Expected-failure planning prompts should stay generic. Division by zero is treated as mathematically undefined, and localhost/loopback navigation without an explicitly running service is treated as unavailable/risky.

Safety/current limits:

- `risk_level=high` or `requires_approval=true` is blocked before any Computer Use step executes.
- Stage05 does not implement the later approval flow; that remains Stage06.
- Unsupported freehand mouse drawing, nonexistent apps, unreachable URLs, and impossible calculations are treated as expected-failure paths in E2E.

Regression tests added:

- `tests/unit/test_planning.py` covers prompt requirements, JSON parsing, and OpenAI Responses API call shape.
- `tests/unit/test_app_operation_log.py` covers WebUI Plan mode routing through `execute_planned_request` and blocking high-risk plans.
- `tests/unit/test_e2e_case_definitions.py` verifies all Stage05 cases are implemented.
- `tests/unit/test_e2e_hid_runner.py` verifies Stage05 uses the WebUI E2E runner.

## Stage06 approval flow

Date: 2026-07-05

Implementation intent:

- Stage06 changes high-risk planning from a hard stop into an approval-pending pause. The plan is held in memory and no Computer Use step runs until the user approves it.
- Approval is separate from the existing Suspend/Resume controls. While approval is pending, Suspend and Resume are disabled/blocked so they cannot be confused with approving the operation.
- Emergency Stop remains available during approval pending and cancels the pending approval as `cancelled_by_emergency_stop`.
- CLI planning has the same safety gate. `controller.py --planning ...` refuses high-risk or approval-required plans unless `--approve-risk` is passed.

Lessons:

- Some high-risk planner responses legitimately contain no executable steps because the model decides the operation should not proceed without approval. Treat these as valid approval-required plans by synthesizing a single approval-required step instead of failing JSON parsing.
- WebUI `/api/command` returns HTTP 200 with `approval_pending=true` for high-risk plans. This keeps the request successful while clearly showing that execution has paused.
- `/api/approve` resumes through the existing planned-step Computer Use path. `/api/reject` and approval timeout clear the pending plan without touching the target PC.
- The Stage06 WebUI E2E runner verifies the safety state through `/api/status`, operation logs, and Suspend/Resume 409 responses before treating approval blocking as green.

Regression tests added:

- `tests/unit/test_app_operation_log.py` covers high-risk approval pending, approve execution, reject, timeout, and the WebUI controls for approval state.
- `tests/unit/test_controller.py` covers CLI planning refusal and `--approve-risk` execution.
- `tests/unit/test_planning.py` covers high-risk responses with empty step lists.
- `tests/unit/test_e2e_case_definitions.py` verifies all Stage06 cases are implemented.
- `tests/unit/test_e2e_hid_runner.py` verifies Stage06 uses the WebUI E2E runner.

## Stage07 email notification

Date: 2026-07-05

Implementation intent:

- Stage07 adds SMTP email notification without changing the existing Computer Use/HID execution paths.
- The WebUI emits email notifications for operation completion, emergency stop, approval request, command error, suspend, and resume.
- Notification failures never fail the main operation. They are recorded in `notification_log` with `sent`, `failed`, `skipped`, or `rate_limited`.
- The email recipient is configurable through `[email].to_addrs`. When it is empty, the SMTP sender account from `/home/nama/mail-send-vert.txt` is used as the recipient, which is the Stage07 test rule.
- `[email].delivery = "console"` prints the email to stdout and records `sent` without opening SMTP. Stage07 E2E uses this mode to avoid external email delivery.

SMTP lessons:

- The Pi5 account file uses `STARTTLS`, `SMTP_SERVER`, `SMTP_PORT`, `SENDER_MAIL`, and `SMTP_PASSWORD`.
- Do not copy SMTP passwords into config files or logs. The parser reads them only for the SMTP login call.
- STARTTLS requires `ehlo()`, `starttls()`, and `ehlo()` before login, matching the sample code.
- Screenshot attachments are omitted when they exceed `[email].attachment_limit_mb`; the notification still sends and records `attachment_policy=omitted`.
- Duplicate notifications for the same event and recipient are suppressed for `[email].min_interval_sec`.

Regression tests added:

- `tests/unit/test_notifications.py` covers SMTP account parsing, self-recipient fallback, success logging, disabled logging, rate limiting, auth failure logging, and attachment omission.
- `tests/unit/test_operation_log.py` covers `notification_log` persistence and query.
- `tests/unit/test_e2e_case_definitions.py` verifies all Stage07 cases are implemented.
- `tests/unit/test_e2e_hid_runner.py` verifies Stage07 uses the WebUI E2E runner.

Validation note:

- Stage07 E2E is run with `.\scripts\ps1\test_e2e_suite.ps1 -Stage stage07_email_notification`.
- The first implementation attempted real SMTP delivery and was rejected by escalation review because it could send operational details or screenshots externally. The E2E runner now forces console delivery for Stage07 success cases and injects a local failing SMTP class for the auth-failure case, so the stage can be tested without external email.

## Stage08 long-running state

Date: 2026-07-05

Implementation intent:

- Stage08 is mostly a confirmation layer over existing WebUI runtime safety. Avoid adding a real long-running executor in this stage.
- The WebUI now exposes a structured `long_operation` object in `/api/status` with progress counters, current step, estimated percent, warning, cancellation, screen-drift, and resume-verification flags.
- Long-operation suspend state is persisted in `runtime_state.json` under `[app].runtime_dir`, so a new Flask app instance can restore the suspended progress state.
- `/api/suspend`, `/api/resume`, and `/api/cancel` update long-operation state without changing the existing Computer Use and HID execution paths.
- `/api/long-operation-test` is a small fixture endpoint used by Stage08 E2E to exercise long-running state without forcing the target PC through artificial long operations.

Lessons:

- Resume after screen drift should not use normal Resume. It enters approval pending and keeps `resume_requires_verification=true`.
- The UI can show progress with the existing Status key/value panel; no large frontend refactor is needed.
- Scenario 6 remains an expected-failure style safety check: a failed long-plan step must be recorded and must not continue blindly.

Regression tests added:

- `tests/unit/test_app_operation_log.py` covers long-operation progress, suspend/resume, cancel, screen-drift approval, and restart persistence.
- `tests/unit/test_e2e_case_definitions.py` verifies all Stage08 cases are implemented.
- `tests/unit/test_e2e_hid_runner.py` verifies Stage08 uses the WebUI E2E runner.

## Stage09 token budget

Date: 2026-07-05

Implementation intent:

- Stage09 keeps the existing Logs page token display as the source of truth. `SYSTEM LOG` and `TOKEN GRAPH` remain linked by timestamp rows; no separate token dashboard is required for this stage.
- `[token_budget]` controls rough token budgeting: `baseline_tokens_per_operation`, `max_tokens_per_operation`, `max_tokens_per_step`, `max_tokens_per_plan`, and `max_tokens_per_day`.
- Plan prediction uses recent rows in `token_usage_log` as the baseline. If no sample exists, it falls back to `baseline_tokens_per_operation`.
- `/api/tokens/predict` exposes the rough estimate for multi-step plans and stores the latest prediction in `/api/status` as `token_prediction`.
- `/api/tokens/check-budget` sends over-budget plans into the existing approval-pending flow instead of inventing a new pause mechanism.
- Missing OpenAI usage metadata is not silently treated as zero. It is recorded as `usage_known=false`, logged as `system_log.event=token_usage/status=unknown`, and given an estimated token count.

Lessons:

- The Stage09 scenarios originally assumed token totals on the top operation screen. After the logs refactor, the accepted display is the current Logs page pairing of `SYSTEM LOG` and `TOKEN GRAPH`, plus aggregate totals from `/api/tokens`.
- For E2E, use WebUI fixture endpoints to validate token accounting without spending OpenAI tokens: `/api/tokens/record-test`, `/api/tokens/missing-usage-test`, `/api/tokens/predict`, and `/api/tokens/check-budget`.
- Budget approval should reuse Stage06 approval state. While token budget approval is pending, normal Suspend/Resume behavior remains governed by the existing approval-pending block.
- Daily totals are tested by querying `/api/tokens?from=...&to=...`; this keeps the reset behavior tied to stored timestamps rather than browser-local rendering.

Regression tests added:

- `tests/unit/test_config.py` verifies the token budget config exists.
- `tests/unit/test_app_operation_log.py` covers plan token prediction, over-budget approval pending, missing usage warnings, and unknown usage extraction.
- `tests/unit/test_e2e_case_definitions.py` verifies all Stage09 cases are implemented.
- `pi/pico_hid_bridge/e2e/runner.py` implements all Stage09 WebUI E2E scenarios.
