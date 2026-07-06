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

## キャプチャのウォームアップ

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

## シナリオ5 の仕様変更履歴

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

## 期待失敗ケース

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

## Computer Use の検証プロンプト

Stage02 中に、確認ステップで Computer Use が `SHIFT` などの操作を返したことがありました。verify step は画面判定だけを求める必要があります。

安定した指示:

```text
コンピューターを操作しない。キー入力、クリック、その他の操作を要求しない。
条件を満たす場合だけ 'True' を返し、それ以外は 'False' を返す。
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

## Stage02 最終検証メモ

日付: 2026-07-04

Stage02 は、Pi 側テストと実機 Hardware E2E の両方が通ったときに完了とします。Stage02 のログ系シナリオは Computer Use の画面判定だけで判断せず、SQLite に残ったレコードを正とします。

完了時に追加した最終確認:

- Stage02-Scenario2 では、`operation_log` に実 HID 操作が含まれている必要があります。`WAIT` だけでは不十分です。
- Stage02-Scenario3 では、`screenshot_log` に `before` と `after` の両方の行が必要です。同じ event のスクリーンショットが 2 枚あるだけでは不十分です。
- Stage02 E2E の各ステップは、必要な before/after capture を取得したあと、画面上の成功判定を `validate_stage02_logs()` に委ねてもよいです。
- Keyboard / text の HID コマンドには短い自動 settle delay を入れ、`WIN+R` の直後に `chrome` を送っても先頭文字が落ちないようにしました。

完了ゲートで使ったコマンド:

```powershell
.\scripts\ps1\test_pytest_call_only_on_pi.ps1 -PytestArgs @('tests/unit/test_e2e_hid_runner.py','tests/unit/test_e2e_case_definitions.py','tests/unit/test_operation_log.py','tests/unit/test_app_operation_log.py','tests/integration/test_operation_log.py','-q')
.\scripts\ps1\test_e2e_suite.ps1 -Stage stage02_operation_log
.\scripts\ps1\test_e2e_suite.ps1 -Stage stage01_core_io
```

## Stage03 / Stage04 完了メモ

日付: 2026-07-04

Stage03 と Stage04 は、WebUI 中心の E2E 経路で確認します。runner は Pi5 上に独立した runtime directory 付きで Flask WebUI app を作成し、`app.test_client()` から WebUI API を呼びます。Computer Use -> Pico UART -> target PC まで通す必要がある Request シナリオでは `/api/command` を使います。これにより、本番の WebUI API 経路をテストしつつ、対象 PC のブラウザ自体に WebUI を操作させずに済みます。

重要な判断:

- Stage03 の emergency stop は Manual HID をブロックします。新しい Request command は emergency stop を解除し、新しい操作として開始します。
- Suspend は、Resume で状態が解除されるまで Manual HID をブロックします。
- 小さな `/api/approval-test` fixture は、Emergency Stop が pending approval を `cancelled_by_emergency_stop` としてキャンセルすることだけを検証するためにあります。
- WebUI は User Log、Operation Log、System Log を別ペインとして表示します。
- Manual HID は、単独の非 WIN 修飾キーとして `KEY ALT`、`KEY CTRL`、`KEY SHIFT` を拒否します。`KEY WIN` は Pico firmware が Windows key の単独押下をサポートしているため許可します。
- WebUI Request は、既知の未対応 freehand mouse-drag request と `DefinitelyNotARealApp12345` failure fixture を、誤って成功扱いせずブロックします。
- `/api/command` は action 実行後も Computer Use turn を継続するため、複数ステップの WebUI Request case が最初の HID batch の先へ進めます。

完了ゲート:

```powershell
.\scripts\ps1\test_pytest_call_only_on_pi.ps1 -PytestArgs @('tests/unit/test_e2e_hid_runner.py','tests/unit/test_e2e_case_definitions.py','tests/unit/test_app_operation_log.py','tests/unit/test_hid_commands.py','tests/unit/test_run_e2e_suite.py','-q')
.\scripts\ps1\test_e2e_suite.ps1 -Stage stage03_runtime_safety
.\scripts\ps1\test_e2e_suite.ps1 -Stage stage04_webui_control
.\scripts\ps1\test_e2e_suite.ps1 -Stage stage02_operation_log
.\scripts\ps1\test_e2e_suite.ps1 -Case stage01_scenario04_calculator_basic
```

## WebUI の常駐キャプチャサービス

日付: 2026-07-05

観測した問題:

- `/api/command` 実行中に WebUI JavaScript の polling が `/api/screenshot` を更新すると、Computer Use 用の screenshot capture が `failed to open capture device: /dev/video0` で失敗することがありました。
- `ffplay` と WebUI 初期画面は正常だったため、原因は hardware や device ID ではなさそうでした。危険だったのは、複数経路からの capture request ごとに `/dev/video0` を開閉していた流れです。
- HDMI capture device を開き直すと、対象 PC 側が display の切断/再接続を検出し、画面点滅や追加 warmup frames が必要になることがあります。

最終設計:

- WebUI mode は app startup 時に `CaptureService` thread を 1 つ起動します。
- service は `/dev/video0` を一度だけ開き、frame を継続的に読み、最新 frame を memory に保持します。
- `/api/screenshot` と Computer Use screenshot response は、どちらも同じ最新 frame を読みます。
- device open/close は WebUI app の startup/shutdown だけで行います。CLI の capture-only 経路は one-shot capture のままでよいです。
- WebUI E2E runner は WebUI case ごとに service を起動し、case 終了後に止めます。これにより、Stage03/Stage04 test が case 間で capture handle を残しません。
- WebUI E2E の開始前に、runner は `python3 app.py` がすでに動いていないか確認します。起動済みの WebUI app が `/dev/video0` を保持していると、test app が capture device を開けなくなります。

追加した回帰テスト:

- `tests/unit/test_capture_service.py` は、`CaptureService` が `VideoCapture` を一度だけ開き、更新 frame を配信し、stop 時に device を release することを検証します。
- `tests/unit/test_app_operation_log.py` は、`/api/screenshot` が共有 service を使い、`/api/command` がその service を Computer Use へ渡すことを検証します。

検証コマンド:

```powershell
.\scripts\ps1\test_pytest_call_only_on_pi.ps1 -PytestArgs @('tests/unit','-q')
.\scripts\ps1\test_e2e_suite.ps1 -Case stage04_scenario01_lan_webui_status
.\scripts\ps1\test_e2e_suite.ps1 -Case stage04_scenario08_webui_request_open_browser
```

追加の live-server 確認:

- Pi5 上で `python3 app.py --host 127.0.0.1 --port 18083` を起動しました。
- `open browser` を `/api/command` へ post している間、0.5 秒ごとに `/api/screenshot` を poll しました。
- 結果: command は 200 を返し、polling screenshot はすべて 200、最後の screenshot も 200 を返しました。

## WebUI の操作画面とログ画面の分割

日付: 2026-07-05

capture と command controls の横に user / operation / system log をすべて表示すると、WebUI の top screen が混みすぎました。現在の UI は 2 つの view に分けています。

- 操作画面: キャプチャ画面、Request / Plan / Manual HID のコマンドモード、状態、suspend/resume、emergency stop。
- ログ画面: 更新と日時検索コントロール、User Log、Operation Log、詳細タイムライン、token usage bar graph。

データの流れ:

- ログ画面は `/api/logs/detail` 経由で SQLite から読みます。
- `system_log` は、それまで memory-only だった system event を永続化します。
- `token_usage_log` は Computer Use response ごとの token usage を保存します。OpenAI usage metadata がない場合、usage を 0 として黙って扱わず、`system_log.event=token_usage/status=unknown` と estimated token count を記録します。
- token graph は CDN dependency ではなく CSS/JavaScript の local bars で描画します。これにより Pi5 WebUI が閉じた LAN 環境でも動きます。
- User Log、Operation Log、詳細 timeline、token graph はすべて newest-first で表示します。
- token graph row は左側 log row の timestamp を使います。各 bar は、時系列で 1 つ前の左側 log timestamp の後から現在の左側 log timestamp までに消費した total tokens を示します。
- Logs toolbar は全期間と現在の browser-local month の consumed tokens aggregate を表示します。From/To が設定されている場合は、その filtered range の aggregate も表示します。これらの total は、表示中の 500 log rows を合計せず、`/api/tokens` で SQLite から query します。

検証:

```powershell
.\scripts\ps1\test_pytest_call_only_on_pi.ps1 -PytestArgs @('tests/unit','-q')
.\scripts\ps1\test_e2e_suite.ps1 -Case stage04_scenario01_lan_webui_status
.\scripts\ps1\test_e2e_suite.ps1 -Case stage04_scenario03_planning_toggle
.\scripts\ps1\test_e2e_suite.ps1 -Case stage04_scenario04_log_panes
```

## Pi パッケージ構成の整理

日付: 2026-07-05

Stage04 の WebUI 作業後、`pi/app.py` と E2E files は entrypoint と implementation が混ざった module になっていました。現在の Pi 側は、`pi/pico_hid_bridge/` 配下で feature ごとに整理しています。

- `pico_hid_bridge/web/`: Flask WebUI implementation と HTML/CSS/JavaScript template。
- `pico_hid_bridge/cli/`: Computer Use controller などの CLI implementation。
- `pico_hid_bridge/e2e/`: E2E model、case definitions、runner implementation。
- `pi/tools/`: hardware-check と test helper command implementation。

旧 `pi/app.py`、`pi/controller.py`、`pi/e2e_cases.py`、`pi/e2e_hid_runner.py`、`pi/run_e2e_case.py`、`pi/run_e2e_suite.py` は、薄い compatibility entrypoint / import wrapper として残します。新しい implementation code はそれらの wrapper ではなく feature package 側へ追加します。

## Stage05 プランニングラッパー

日付: 2026-07-05

実装意図:

- Stage05 は既存の Computer Use flow を置き換えずに planning を追加します。
- 新しい wrapper は 1 つの user request を受け取り、OpenAI API に JSON plan を依頼し、返ってきた各 step を通常の Request mode と同じ `execute_computer_use_request` 経路へ送ります。
- planner は低レベル HID command を出してはいけません。生の `KEY`、`TEXT`、`MOUSE_MOVE`、`CLICK` command は Manual HID の責務です。
- prompt は generic に保ちます。単一の E2E scenario 向けに tuning せず、挙動が悪い場合は execution code を変える前に generic planning prompt を見直します。

Prompt / API の教訓:

- planning request は、`risk_level`、`requires_approval`、`summary`、`steps` を持つ `pc_operation_plan` schema の structured JSON output を使います。
- 各 step は既存 Computer Use executor 向けの自然言語 instruction であり、Pico 向けの action list ではありません。
- planner request では reasoning effort を有効にし、model が multi-step decomposition を考えてから JSON result を出せるようにします。
- prompt では keyboard-friendly な Windows workflow を強く優先します。application 起動は `WIN+R`、active window 切り替えは `ALT+TAB` を使います。
- Computer Use prompt には、未対応 HID choices を明示する必要があります。Stage05 で `PAGEDOWN` と `drag` action が露出したため、prompt は supported keys を列挙し、page navigation keys や drag を使わないよう明記しています。
- Computer Use は research / summarize step に対して、PC を操作せず自然言語で答えることがあります。WebUI execution path は、computer tool actions を使い、summary を物理 PC へ type するよう強めた instruction で 1 回 retry します。
- Computer Use は summary 用に長い、または multiline の `type` action を出すことがあります。`ActionExecutor` は multiline text を `TEXT` と `KEY ENTER` に分け、長文 text を 256 文字の `TEXT` line に分割します。その下の UART layer が各 line を 20 文字の Pico batch に分けます。
- expected-failure planning prompt は generic なままにします。division by zero は数学的に undefined と扱い、明示的に service が動いていない localhost / loopback navigation は unavailable / risky と扱います。

安全性と現在の制限:

- `risk_level=high` または `requires_approval=true` は、Computer Use step 実行前にブロックします。
- Stage05 では後続の approval flow は実装しません。それは Stage06 の範囲です。
- 未対応の freehand mouse drawing、存在しない app、到達不能 URL、不可能な計算は、E2E では expected-failure path として扱います。

追加した回帰テスト:

- `tests/unit/test_planning.py` は prompt requirements、JSON parsing、OpenAI Responses API call shape をカバーします。
- `tests/unit/test_app_operation_log.py` は WebUI Plan mode が `execute_planned_request` を通ることと high-risk plan blocking をカバーします。
- `tests/unit/test_e2e_case_definitions.py` は Stage05 の全 case が実装済みであることを検証します。
- `tests/unit/test_e2e_hid_runner.py` は Stage05 が WebUI E2E runner を使うことを検証します。

## Stage06 承認フロー

日付: 2026-07-05

実装意図:

- Stage06 では、high-risk planning を hard stop ではなく approval-pending pause に変更します。plan は memory に保持し、user が approve するまで Computer Use step は実行しません。
- Approval は既存の Suspend / Resume controls とは別です。approval pending 中は Suspend と Resume を disabled / blocked にし、operation approval と混同されないようにします。
- Emergency Stop は approval pending 中も利用可能で、pending approval を `cancelled_by_emergency_stop` としてキャンセルします。
- CLI planning も同じ safety gate を持ちます。`controller.py --planning ...` は、`--approve-risk` が渡されない限り high-risk plan や approval-required plan を拒否します。

教訓:

- high-risk planner response には、model が approval なしでは進めるべきでないと判断した結果、実行可能 step が 0 件になる正当な case があります。これらは JSON parsing failure にせず、approval-required step を 1 つ合成して valid approval-required plan として扱います。
- WebUI `/api/command` は high-risk plan に対して `approval_pending=true` 付きの HTTP 200 を返します。request 自体は成功させつつ、execution が pause したことを明確に示します。
- `/api/approve` は既存の planned-step Computer Use path を通って再開します。`/api/reject` と approval timeout は、target PC に触れず pending plan を clear します。
- Stage06 WebUI E2E runner は、approval blocking を green と扱う前に、`/api/status`、operation logs、Suspend / Resume の 409 response で safety state を検証します。

追加した回帰テスト:

- `tests/unit/test_app_operation_log.py` は high-risk approval pending、approve execution、reject、timeout、approval state 用 WebUI controls をカバーします。
- `tests/unit/test_controller.py` は CLI planning refusal と `--approve-risk` execution をカバーします。
- `tests/unit/test_planning.py` は empty step list を持つ high-risk response をカバーします。
- `tests/unit/test_e2e_case_definitions.py` は Stage06 の全 case が実装済みであることを検証します。
- `tests/unit/test_e2e_hid_runner.py` は Stage06 が WebUI E2E runner を使うことを検証します。

## Stage07 メール通知

日付: 2026-07-05

実装意図:

- Stage07 は既存の Computer Use / HID execution path を変えずに SMTP email notification を追加します。
- WebUI は operation completion、emergency stop、approval request、command error、suspend、resume に対して email notification を出します。
- notification failure は main operation を失敗させません。`notification_log` に `sent`、`failed`、`skipped`、`rate_limited` として記録します。
- email recipient は `[email].to_addrs` で設定できます。空の場合は `/home/nama/mail-send-vert.txt` の SMTP sender account を recipient として使います。これは Stage07 の test rule です。
- `[email].delivery = "console"` は SMTP を開かず、email を stdout に出力して `sent` を記録します。Stage07 E2E は external email delivery を避けるため、この mode を使います。

SMTP の教訓:

- Pi5 account file は `STARTTLS`、`SMTP_SERVER`、`SMTP_PORT`、`SENDER_MAIL`、`SMTP_PASSWORD` を使います。
- SMTP password は config file や log にコピーしません。parser は SMTP login call のためだけに読みます。
- STARTTLS では sample code に合わせ、login 前に `ehlo()`、`starttls()`、`ehlo()` が必要です。
- screenshot attachment が `[email].attachment_limit_mb` を超える場合は添付を省略します。notification 自体は送信し、`attachment_policy=omitted` を記録します。
- 同じ event と recipient に対する duplicate notification は `[email].min_interval_sec` の間は抑制します。

追加した回帰テスト:

- `tests/unit/test_notifications.py` は SMTP account parsing、self-recipient fallback、success logging、disabled logging、rate limiting、auth failure logging、attachment omission をカバーします。
- `tests/unit/test_operation_log.py` は `notification_log` persistence と query をカバーします。
- `tests/unit/test_e2e_case_definitions.py` は Stage07 の全 case が実装済みであることを検証します。
- `tests/unit/test_e2e_hid_runner.py` は Stage07 が WebUI E2E runner を使うことを検証します。

検証メモ:

- Stage07 E2E は `.\scripts\ps1\test_e2e_suite.ps1 -Stage stage07_email_notification` で実行します。
- 最初の実装では real SMTP delivery を試しましたが、operational details や screenshots を外部送信し得るため escalation review で拒否されました。現在の E2E runner は Stage07 success case で console delivery を強制し、auth-failure case では local failing SMTP class を注入します。これにより external email なしで stage をテストできます。

## Stage08 長時間操作状態

日付: 2026-07-05

実装意図:

- Stage08 は主に既存 WebUI runtime safety の確認 layer です。この stage では real long-running executor を追加しません。
- WebUI は `/api/status` に structured `long_operation` object を出します。そこには progress counters、current step、estimated percent、warning、cancellation、screen-drift、resume-verification flags が含まれます。
- long-operation の suspend state は `[app].runtime_dir` 配下の `runtime_state.json` に永続化します。これにより、新しい Flask app instance が suspended progress state を restore できます。
- `/api/suspend`、`/api/resume`、`/api/cancel` は、既存の Computer Use と HID execution path を変えずに long-operation state を更新します。
- `/api/long-operation-test` は、target PC に artificial long operation を強制せず long-running state を exercise するための Stage08 E2E 用 fixture endpoint です。

教訓:

- screen drift 後の Resume は通常の Resume を使いません。approval pending に入り、`resume_requires_verification=true` を保持します。
- UI は既存の Status key/value panel で progress を表示できます。大きな frontend refactor は不要です。
- Scenario 6 は expected-failure style の safety check のままです。failed long-plan step は記録される必要があり、盲目的に続行してはいけません。

追加した回帰テスト:

- `tests/unit/test_app_operation_log.py` は long-operation progress、suspend/resume、cancel、screen-drift approval、restart persistence をカバーします。
- `tests/unit/test_e2e_case_definitions.py` は Stage08 の全 case が実装済みであることを検証します。
- `tests/unit/test_e2e_hid_runner.py` は Stage08 が WebUI E2E runner を使うことを検証します。

## Stage09 トークン予算

日付: 2026-07-05

実装意図:

- Stage09 では、既存 Logs page の token display を正とします。`SYSTEM LOG` と `TOKEN GRAPH` は timestamp rows で連動したままで、独立した token dashboard はこの stage では不要です。
- `[token_budget]` は rough token budgeting を制御します。項目は `baseline_tokens_per_operation`、`max_tokens_per_operation`、`max_tokens_per_step`、`max_tokens_per_plan`、`max_tokens_per_day` です。
- plan prediction は `token_usage_log` の recent rows を baseline として使います。sample がない場合は `baseline_tokens_per_operation` に fallback します。
- `/api/tokens/predict` は multi-step plan の rough estimate を公開し、latest prediction を `/api/status` に `token_prediction` として保存します。
- `/api/tokens/check-budget` は新しい pause mechanism を作らず、over-budget plan を既存の approval-pending flow へ送ります。
- OpenAI usage metadata がない場合、黙って 0 扱いしません。`usage_known=false` として記録し、`system_log.event=token_usage/status=unknown` に log し、estimated token count を付けます。

教訓:

- Stage09 scenarios は当初、top operation screen に token totals が出る前提でした。logs refactor 後の受け入れ表示は、現在の Logs page における `SYSTEM LOG` と `TOKEN GRAPH` の組み合わせ、および `/api/tokens` からの aggregate totals です。
- E2E では、OpenAI tokens を消費せず token accounting を検証するため、WebUI fixture endpoints の `/api/tokens/record-test`、`/api/tokens/missing-usage-test`、`/api/tokens/predict`、`/api/tokens/check-budget` を使います。
- budget approval は Stage06 の approval state を再利用します。token budget approval pending 中も、通常の Suspend / Resume behavior は既存 approval-pending block に従います。
- daily totals は `/api/tokens?from=...&to=...` を query してテストします。これにより、reset behavior は browser-local rendering ではなく stored timestamps に結び付きます。

追加した回帰テスト:

- `tests/unit/test_config.py` は token budget config が存在することを検証します。
- `tests/unit/test_app_operation_log.py` は plan token prediction、over-budget approval pending、missing usage warnings、unknown usage extraction をカバーします。
- `tests/unit/test_e2e_case_definitions.py` は Stage09 の全 case が実装済みであることを検証します。
- `pi/pico_hid_bridge/e2e/runner.py` は Stage09 WebUI E2E scenarios をすべて実装しています。
