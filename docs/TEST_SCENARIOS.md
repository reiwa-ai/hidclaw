# 開発ステップ別テストシナリオ

この文書は、開発ステップごとの E2E テストシナリオ台帳です。各 Stage は機能を網羅するため、`StageN-ScenarioM` の複数ケースに分けます。実装済みケースは回帰確認として継続実行し、未実装ステージのケースは TDD のひな形として `pending` 状態で管理します。

## 基本方針

各 E2E ケースは、次の流れを 1 ステップまたは複数ステップに分けて実行します。

```text
0. テスト開始前に ALT+F4 と N を複数回送り、対象 PC のウィンドウを閉じる
1. スクリーンキャプチャを撮る
2. Computer Use API に現在画面と action_task を渡して、次の PC 操作を得る
3. 得られた操作を Pico 経由で対象 PC へ送る
4. 再びスクリーンキャプチャを撮る
5. Computer Use API に verify_task を渡し、True / False だけで判定する
6. 全ステップが True ならケース全体を OK にする
```

判定用の `verify_task` には必ず「Do not control the computer」を含め、確認中に PC 操作を進めないようにします。

開始前クリーンアップでは、保存確認ダイアログなどが表示された場合に「いいえ」を選ぶため `KEY N` を送ります。既定では `KEY ALT+F4` と `KEY N` の組み合わせを8回、0.5秒間隔で送ります。

対象 PC へ入力されるテスト指示、検索語、テキストエディタへ入力する本文は、すべて ASCII の英語にします。Pico が HID キーボードをエミュレートするため、日本語 IME 入力を前提にしません。

## 確定したテスト方針

```text
T-001 プランニングE2Eの検索テーマは、安定しやすいテーマを複数使う。
      一般Web、Google指定、Wikipedia指定、arXiv指定のパターンを作る。
T-002 テキストエディタは Windows Notepad 固定ではなく、Computer Use API に
      "text editor" と指定したときに開かれるアプリを使う。
T-003 検索エンジン指定なしのシナリオと、Google などを明示指定するシナリオを分ける。
T-004 メール通知テストは実受信確認までは必須にせず、SMTP送信成功ログでOKにする。
T-005 メール通知の宛先は SMTP アカウント自身にする。
T-006 Discord のギルド、チャンネル、許可ユーザーは設定ファイルで指定し、
      テスト時にはプロジェクト設定を使う。
T-007 対象PCへ入力する文字列は、検索語、ユーザー指示、本文を含めて ASCII English にする。
T-008 `expected_failure` を含むケースは、対象操作が成功しないこと自体が期待結果。
      失敗、拒否、未対応、到達不能、権限エラーなどが画面またはログで確認できたらテスト成功にする。
```

## ケース定義

ケース定義の実体は `pi/pico_hid_bridge/e2e/cases.py` に置きます。`pi/e2e_cases.py` は既存import互換の薄いラッパーです。

```text
E2ETestCase
  name             CLI で指定するケース名
  stage            開発ステージ名
  description      何を保証するか
  implemented      実行可能なら true、TDD ひな形なら false
  pending_reason   未実装理由
  requires         実行に必要な外部条件
  steps            E2EStep の列

E2EStep
  name             ステップ名
  action_task      Computer Use API に PC 操作を依頼する指示
  verify_task      スクリーンキャプチャから True / False を返す判定指示
  success_message  True のときの意味
  failure_message  False のときの意味
```

`implemented = false` のケースは、既定の回帰テストではスキップします。TDD でそのステージを開始するときは `--include-pending` を付けて意図的に赤として実行します。

## 実行コマンド

Pi 5 上のケース一覧を確認:

```powershell
.\scripts\ps1\test_e2e_suite.ps1 -List
```

実装済みケースだけを回帰実行:

```powershell
.\scripts\ps1\test_e2e_suite.ps1
```

特定ステージだけを実行:

```powershell
.\scripts\ps1\test_e2e_suite.ps1 -Stage stage05_planning
```

TDD 開始時に pending ケースを含めて実行:

```powershell
.\scripts\ps1\test_e2e_suite.ps1 -Case stage05_scenario02_google_http_status_codes
```

Pi 5 側で直接実行:

```sh
cd /home/nama/pi
python3 run_e2e_suite.py --list
python3 run_e2e_suite.py --case open_browser_e2e --api-key-file /home/nama/openai-api-key.txt
```

## Stage 1: Core I/O

目的: キャプチャー、Computer Use API、Pico HID、再キャプチャー、画面判定の基本ループを保証します。

| Scenario | ケース名 | 状態 | 目的 |
| --- | --- | --- | --- |
| Stage1-Scenario1 | `stage01_scenario01_open_browser` | implemented | ブラウザ起動の基本E2Eループ |
| Stage1-Scenario2 | `stage01_scenario02_run_dialog_shortcut` | implemented | WIN+R など修飾キー付きショートカット |
| Stage1-Scenario3 | `stage01_scenario03_text_editor_input` | implemented | テキストエディタへのASCII入力 |
| Stage1-Scenario4 | `stage01_scenario04_calculator_basic` | implemented | 電卓を開いて基本計算 |
| Stage1-Scenario5 | `stage01_scenario05_paint_text` | implemented | Paintで既存画像を開き、画像内テキストを確認 |
| Stage1-Scenario6 | `stage01_scenario06_expected_failure_unsupported_drag` | implemented | 期待失敗: 未対応のPaintドラッグを拒否 |
| Stage1-Scenario7 | `stage01_scenario07_expected_failure_nonexistent_app` | implemented | 期待失敗: 存在しないアプリを失敗として扱う |

補助ユニット/統合テスト:

| Scenario | テスト | 状態 | 目的 |
| --- | --- | --- | --- |
| Stage1-Scenario8 | `tests/unit/test_hid_commands.py::test_wait_for_pico_ack_times_out_without_ack` | implemented | Pico ACK timeout を検出して無限待ちしない |
| Stage1-Scenario9 | `tests/integration/test_pi_environment.py::test_pi_pico_uart_smoke` | implemented | 対象PCに入力しない `PING` で Pico UART 疎通を確認 |

```text
Stage1-Scenario1:
  Step1: スクリーンキャプチャを撮り、Computer Use API へ "Open Browser" を依頼する
  Step2: 返された操作を Pico に送り、対象 PC を操作する
  Step3: 再キャプチャーし、ブラウザ表示を True / False 判定する

Stage1-Scenario2:
  Step1: Computer Use API に "Open the Windows Run dialog" を依頼する
  Step2: Pico へ修飾キー付き HID 操作を送る
  Step3: Run ダイアログが表示されているか判定する

Stage1-Scenario3:
  Step1: Computer Use API に text editor を開くよう依頼する
  Step2: Pico 経由で "Pico HID test 123" を入力する
  Step3: テキストが入力されているか判定する

Stage1-Scenario4:
  Step1: Computer Use API に "Open Calculator" を依頼する
  Step2: "123 plus 456" を計算する
  Step3: 電卓に 579 が表示されているか判定する

Stage1-Scenario5:
  Step1: Computer Use API に Paint を開くよう依頼する
  Step2: 空の Paint で `CTRL+O` から開くダイアログを出し、`C:\Users\user\Pictures\test.png` を読み込むよう依頼し、画像ファイルが表示されているか判定する
  Step3: 画像内に "This is test" が描かれているか判定する

Stage1-Scenario6:
  Step1: Paint でマウスドラッグによる斜線描画を要求する
  Step2: 現在未対応のドラッグ操作が unsupported として報告されるか、未対応としてブロックされることを判定する
  Step3: unsupported / blocked が確認できたら expected failure 検出としてテスト成功

Stage1-Scenario7:
  Step1: "DefinitelyNotARealApp12345" を開くよう要求する
  Step2: アプリが開かず、not found または failure として報告されるか判定する
  Step3: 失敗が確認できたら expected failure 検出としてテスト成功

Stage1-Scenario8:
  Step1: ACK を返さない fake serial を使う
  Step2: `wait_for_pico_ack` が TimeoutError を返すことを確認する
  Step3: ACK 待ちが無限化しないことを保証する

Stage1-Scenario9:
  Step1: Pi5 から Pico へ `PING` を送る
  Step2: 対象PCへ HID 入力を送らずに `PICO_HID_OK` が返ることを確認する
  Step3: Pico UART の復帰確認に `KEY ESC` ではなく `PING` を使えることを保証する
```

## Stage 2: SQLite 操作ログ

目的: ユーザー入力ログ、PC操作ログ、スクリーンショットログ、容量制限を分けて保証します。

| Scenario | ケース名 | 状態 | 目的 |
| --- | --- | --- | --- |
| Stage2-Scenario1 | `stage02_scenario01_user_input_log` | implemented | ユーザー入力ログ |
| Stage2-Scenario2 | `stage02_scenario02_operation_log` | implemented | HID操作ログ |
| Stage2-Scenario3 | `stage02_scenario03_screenshot_log` | implemented | 操作前後スクリーンショットログ |
| Stage2-Scenario4 | `stage02_scenario04_storage_limit` | implemented | 設定ファイルの最大容量に基づくローテーション |
| Stage2-Scenario5 | `stage02_scenario05_error_log` | implemented | 失敗操作のエラーログ |
| Stage2-Scenario6 | `stage02_scenario06_log_query_filters` | implemented | ログの絞り込み |
| Stage2-Scenario7 | `stage02_scenario07_expected_failure_corrupt_db_recovery` | implemented | 期待失敗: 壊れたDBの安全検出 |

```text
Stage2-Scenario1:
  Step1: 通常パイプラインからブラウザ起動指示を実行する
  Step2: Pi5側SQLiteの user_input_log に指示内容、送信元、ケース名が記録されているか判定する

Stage2-Scenario2:
  Step1: HID 操作を含む短い操作を実行する
  Step2: Pi5側SQLiteの operation_log に実際の HID コマンド、結果、エラー有無が記録されているか判定する

Stage2-Scenario3:
  Step1: 主要イベントが発生する操作を実行する
  Step2: Pi5側SQLiteの screenshot_log に操作前後のスクリーンショット履歴が記録されているか判定する

Stage2-Scenario4:
  Step1: テスト用の小さい最大保持数で複数スクリーンショットログを作る
  Step2: 古いスクリーンショットログと対応ファイルが容量制限に従って整理されたか判定する

Stage2-Scenario5:
  Step1: 存在しないアプリを開く expected_failure 操作を実行する
  Step2: operation_log と error_log に failed status、理由、対象ケースIDが記録されているか判定する

Stage2-Scenario6:
  Step1: 成功操作と失敗操作をそれぞれ記録する
  Step2: source、status、case name でログを絞り込み、該当ログだけが取得できるか判定する

Stage2-Scenario7:
  Step1: テスト用の壊れた SQLite DB で起動する
  Step2: DB破損が検出され、壊れたDBが退避され、新しいDBでログ記録を継続できることを判定する
  Step3: 安全に失敗を報告できたらテスト成功
```

## Stage 3: 非常停止と状態管理

目的: 非常停止、次コマンドでの新規開始、サスペンド/レジューム、承認待ちキャンセルを保証します。

| Scenario | ケース名 | 状態 | 目的 |
| --- | --- | --- | --- |
| Stage3-Scenario1 | `stage03_scenario01_emergency_stop_blocks_hid` | implemented | 非常停止で HID 送信を止める |
| Stage3-Scenario2 | `stage03_scenario02_new_command_resets_state` | implemented | 新規コマンドで過去状態を忘れる |
| Stage3-Scenario3 | `stage03_scenario03_suspend_resume_state` | implemented | サスペンド/レジューム状態遷移 |
| Stage3-Scenario4 | `stage03_scenario04_stop_cancels_pending_approval` | implemented | 非常停止で承認待ちをキャンセル |

```text
Stage3-Scenario1:
  Step1: 実行中または待機中の操作に対して非常停止を発火する
  Step2: 非常停止状態が表示され、PC 操作が進まないことを判定する

Stage3-Scenario2:
  Step1: 非常停止後に新しいブラウザ起動コマンドを入力する
  Step2: 過去のプロセスを引き継がず、新しい操作として実行されることを判定する

Stage3-Scenario3:
  Step1: 操作をサスペンドし、レジュームする
  Step2: 状態遷移とシステムイベントログが見えることを判定する

Stage3-Scenario4:
  Step1: 承認待ち操作を作成し、非常停止を発火する
  Step2: 承認待ちが cancelled_by_emergency_stop になり、PC 操作が進まないことを判定する
```

## Stage 4: WebUI 制御

目的: LAN 限定 WebUI の表示、Request タブからの Computer Use 操作、Manual HID タブからの低レベル操作、トグル、ログ閲覧を保証します。

| Scenario | ケース名 | 状態 | 目的 |
| --- | --- | --- | --- |
| Stage4-Scenario1 | `stage04_scenario01_lan_webui_status` | implemented | LAN WebUI の状態とキャプチャー表示 |
| Stage4-Scenario2 | `stage04_scenario02_manual_hid_command` | implemented | WebUI からの手動 HID コマンド |
| Stage4-Scenario3 | `stage04_scenario03_planning_toggle` | implemented | プランニング ON/OFF トグル |
| Stage4-Scenario4 | `stage04_scenario04_log_panes` | implemented | ユーザー/操作/システムログの分離表示 |
| Stage4-Scenario5 | `stage04_scenario05_expected_failure_invalid_hid_command` | implemented | 期待失敗: 不正HIDコマンド拒否 |
| Stage4-Scenario6 | `stage04_scenario06_webui_emergency_button` | implemented | WebUI非常停止ボタン |
| Stage4-Scenario7 | `stage04_scenario07_refresh_screenshot` | implemented | WebUIスクリーンショット更新 |
| Stage4-Scenario8 | `stage04_scenario08_webui_request_open_browser` | implemented | Stage01ブラウザ起動をWebUI Request経由で再確認 |
| Stage4-Scenario9 | `stage04_scenario09_webui_request_run_dialog` | implemented | Stage01 Runダイアログ操作をWebUI Request経由で再確認 |
| Stage4-Scenario10 | `stage04_scenario10_webui_request_text_editor_input` | implemented | Stage01テキストエディタ入力をWebUI Request経由で再確認 |
| Stage4-Scenario11 | `stage04_scenario11_webui_request_calculator_basic` | implemented | Stage01電卓操作をWebUI Request経由で再確認 |
| Stage4-Scenario12 | `stage04_scenario12_webui_request_paint_text` | implemented | Stage01 Paint画像確認をWebUI Request経由で再確認 |
| Stage4-Scenario13 | `stage04_scenario13_webui_request_expected_failure_unsupported_drag` | implemented | Stage01期待失敗: 未対応ドラッグをWebUI Request経由で再確認 |
| Stage4-Scenario14 | `stage04_scenario14_webui_request_expected_failure_nonexistent_app` | implemented | Stage01期待失敗: 存在しないアプリをWebUI Request経由で再確認 |

```text
Stage4-Scenario1:
  Step1: ブラウザで Raspberry Pi 5 の LAN アドレスの WebUI を開く
  Step2: スクリーンキャプチャ、状態、Request 入力、Manual HID タブが表示されているか判定する

Stage4-Scenario2:
  Step1: WebUI の Manual HID 入力から KEY WIN+R を送る
  Step2: Run ダイアログと操作ログが表示されているか判定する

Stage4-Scenario3:
  Step1: WebUI でプランニングを ON、OFF に切り替える
  Step2: 状態表示に反映されているか判定する

Stage4-Scenario4:
  Step1: 短い操作後に WebUI のログ欄を表示する
  Step2: ユーザー入力、PC 操作、システムイベントが分離表示されているか判定する

Stage4-Scenario5:
  Step1: WebUI の Manual HID 入力から不正な HID コマンドを送ろうとする
  Step2: バリデーションエラーになり、HID送信されないことを判定する
  Step3: 拒否が確認できたらテスト成功

Stage4-Scenario6:
  Step1: WebUI の Emergency Stop を実行する
  Step2: 状態が emergency stopped になり、以後のコマンド入力がブロックされるか判定する

Stage4-Scenario7:
  Step1: 対象PC側で Calculator を開く
  Step2: WebUI のスクリーンショット更新を実行する
  Step3: WebUIのキャプチャー表示が新しい画面へ更新されたか判定する

Stage4-Scenario8:
  Step1: WebUI の Request タブに `open browser` を入力して Send する
  Step2: Current Status と Operation Log が完了状態になるまで待つ
  Step3: WebUI のキャプチャー表示で対象PCにブラウザが表示されているか判定する

Stage4-Scenario9:
  Step1: WebUI の Request タブから Windows Run ダイアログを開くよう依頼する
  Step2: Run ダイアログが WebUI のキャプチャー表示に出ているか判定する
  Step3: Operation Log に Request 経由の操作完了が残るか判定する

Stage4-Scenario10:
  Step1: WebUI の Request タブからテキストエディタを開き `Pico HID test 123` を入力するよう依頼する
  Step2: WebUI のキャプチャー表示にテキストエディタと文字列が見えるか判定する
  Step3: Request 実行中に Send が連打できず、完了後に復帰するか判定する

Stage4-Scenario11:
  Step1: WebUI の Request タブから Calculator を開き `123+456` を計算するよう依頼する
  Step2: WebUI のキャプチャー表示に Calculator の結果 579 が見えるか判定する
  Step3: Operation Log に WebUI Request と Pico HID 操作が残るか判定する

Stage4-Scenario12:
  Step1: WebUI の Request タブから Paint を開き、空のPaintで `CTRL+O` から `C:\Users\user\Pictures\test.png` を開くよう依頼する
  Step2: WebUI のキャプチャー表示に Paint と画像が見えるか判定する
  Step3: 画像内に `This is test` が見えるか判定する

Stage4-Scenario13:
  Step1: WebUI の Request タブから Paint の未対応ドラッグ描画を依頼する
  Step2: WebUI が unsupported / blocked / failed として報告するか判定する
  Step3: 成功扱いにせず expected failure として検出できるか判定する

Stage4-Scenario14:
  Step1: WebUI の Request タブから `DefinitelyNotARealApp12345` を開くよう依頼する
  Step2: WebUI が not found / failed / blocked として報告するか判定する
  Step3: 成功扱いにせず expected failure として検出できるか判定する
```

## Stage 5: プランニング

目的: 複雑な自然言語指示を複数ステップの画面操作へ分解し、検索対象や検索エンジン指定の違いを保証します。

| Scenario | ケース名 | 状態 | 目的 |
| --- | --- | --- | --- |
| Stage5-Scenario1 | `stage05_scenario01_default_web_raspberry_pi_pico` | implemented | 検索エンジン指定なし、一般Web検索 |
| Stage5-Scenario2 | `stage05_scenario02_google_http_status_codes` | implemented | Google 指定検索 |
| Stage5-Scenario3 | `stage05_scenario03_wikipedia_ada_lovelace` | implemented | Wikipedia 指定検索 |
| Stage5-Scenario4 | `stage05_scenario04_arxiv_attention_paper` | implemented | arXiv 指定検索 |
| Stage5-Scenario5 | `stage05_scenario05_planning_disabled_single_step` | implemented | プランニング OFF 時の自動複数ステップ抑止 |
| Stage5-Scenario6 | `stage05_scenario06_calculator_plan` | implemented | 電卓で計算するプラン |
| Stage5-Scenario7 | `stage05_scenario07_paint_text_plan` | implemented | Paintに文字を書くプラン |
| Stage5-Scenario8 | `stage05_scenario08_calculator_to_editor` | implemented | 電卓結果をテキストエディタへ書く複数アプリプラン |
| Stage5-Scenario9 | `stage05_scenario09_browser_to_paint_label` | implemented | ブラウザ検索結果からPaintへラベルを書くプラン |
| Stage5-Scenario10 | `stage05_scenario10_expected_failure_unreachable_url` | implemented | 期待失敗: 到達不能URL |
| Stage5-Scenario11 | `stage05_scenario11_expected_failure_missing_app` | implemented | 期待失敗: 存在しないアプリを含むプラン |
| Stage5-Scenario12 | `stage05_scenario12_expected_failure_calculator_divide_by_zero` | implemented | 期待失敗: 電卓の0除算 |
| Stage5-Scenario13 | `stage05_scenario13_expected_failure_paint_freehand` | implemented | 期待失敗: 未対応のPaint自由描画 |

```text
Stage5-Scenario1:
  Step1: Create the plan "Research Raspberry Pi Pico HID keyboard emulation and summarize it in a text editor."
  Step2: 既定ブラウザの既定検索で一般Web検索する
  Step3: text editor を開き、検索結果の要約を書く
  Step4: 要約文が入力されているか判定する

Stage5-Scenario2:
  Step1: Create the plan "Use Google to research HTTP status codes and summarize the result in a text editor."
  Step2: Google の検索結果が表示されているか判定する
  Step3: text editor に HTTP ステータス分類の要約を書く
  Step4: 要約文が入力されているか判定する

Stage5-Scenario3:
  Step1: Create the plan "Use Wikipedia to research Ada Lovelace and summarize the result in a text editor."
  Step2: Wikipedia の Ada Lovelace ページまたは検索結果を表示する
  Step3: text editor に要約を書く
  Step4: 要約文が入力されているか判定する

Stage5-Scenario4:
  Step1: Create the plan "Use arXiv to search for Attention Is All You Need and summarize the paper information in a text editor."
  Step2: arXiv の検索結果または論文ページを表示する
  Step3: text editor に要約を書く
  Step4: 要約文が入力されているか判定する

Stage5-Scenario5:
  Step1: With planning OFF, input the instruction "Research HTTP status codes and summarize the result in a text editor."
  Step2: 自動で長いプランが実行されず、確認待ち、拒否、または単発扱いになることを判定する

Stage5-Scenario6:
  Step1: Create the plan "Open Calculator and calculate 128 times 7 plus 3."
  Step2: Calculator を開き、式を入力する
  Step3: 結果 899 が表示されているか判定する

Stage5-Scenario7:
  Step1: Create the plan "Open Paint and write HELLO 2026 on the canvas."
  Step2: Paint を開き、キャンバスへ "HELLO 2026" を置く
  Step3: Paint に "HELLO 2026" が表示されているか判定する

Stage5-Scenario8:
  Step1: Create the plan "Calculate 42 times 17, then write the result in a text editor."
  Step2: Calculator で 42 * 17 を計算する
  Step3: text editor を開き、"Result: 714" を入力する
  Step4: text editor に "Result: 714" が表示されているか判定する

Stage5-Scenario9:
  Step1: Create the plan "Search for RGB color names, then open Paint and write RED GREEN BLUE."
  Step2: ブラウザで RGB color names を検索する
  Step3: Paint を開き、"RED GREEN BLUE" を置く
  Step4: Paint に "RED GREEN BLUE" が表示されているか判定する

Stage5-Scenario10:
  Step1: ブラウザで `http://127.0.0.1:9/expected-failure-test` を開く
  Step2: connection error または page could not be reached が表示されるか判定する
  Step3: 到達不能が確認できたらテスト成功

Stage5-Scenario11:
  Step1: "DefinitelyNotARealApp12345" を含むプランを作って実行する
  Step2: 該当ステップが failed になり、成功扱いで先へ進まないことを判定する
  Step3: 失敗ステップを安全に扱えたらテスト成功

Stage5-Scenario12:
  Step1: Calculator で "5 divided by 0" を計算する
  Step2: エラーまたは invalid-result state が表示されるか判定する
  Step3: エラー状態を正しく認識できたらテスト成功

Stage5-Scenario13:
  Step1: Paint で freehand mouse movement による spiral 描画を要求する
  Step2: 未対応操作としてブロックまたは unsupported 報告されるか判定する
  Step3: 未対応を正しく扱えたらテスト成功
```

## Stage 6: 承認フロー

目的: 高リスク操作が承認なしに進まないこと、承認/否認/期限切れが正しく働くことを保証します。

| Scenario | ケース名 | 状態 | 目的 |
| --- | --- | --- | --- |
| Stage6-Scenario1 | `stage06_scenario01_file_save_requires_approval` | implemented | ファイル保存の承認要求 |
| Stage6-Scenario2 | `stage06_scenario02_send_or_post_requires_approval` | implemented | 送信/投稿/submit の承認要求 |
| Stage6-Scenario3 | `stage06_scenario03_login_requires_approval` | implemented | ログイン/認証/個人情報入力の承認要求 |
| Stage6-Scenario4 | `stage06_scenario04_reject_prevents_execution` | implemented | 否認で実行されないこと |
| Stage6-Scenario5 | `stage06_scenario05_approval_timeout` | implemented | 承認待ち期限切れ |
| Stage6-Scenario6 | `stage06_scenario06_delete_requires_approval` | implemented | ファイル削除の承認要求 |
| Stage6-Scenario7 | `stage06_scenario07_install_requires_approval` | implemented | インストール/設定変更の承認要求 |
| Stage6-Scenario8 | `stage06_scenario08_safe_read_no_approval` | implemented | 安全な読み取り操作は承認不要 |
| Stage6-Scenario9 | `stage06_scenario09_expected_failure_unapproved_action` | implemented | 期待失敗: 未承認の危険操作は実行されない |

```text
Stage6-Scenario1:
  Step1: Input the instruction "Write a short note in a text editor and save it to a file."
  Step2: 保存前に承認待ちになり、保存が完了していないことを判定する

Stage6-Scenario2:
  Step1: Input the instruction "Type a short message and submit it."
  Step2: 実行前に承認待ちになることを判定する

Stage6-Scenario3:
  Step1: Input the instruction "Log in with a username and password."
  Step2: 入力前に承認待ちになることを判定する

Stage6-Scenario4:
  Step1: 承認待ち操作を作る
  Step2: 否認する
  Step3: 危険操作が実行されず、approval_log に rejected が残ることを判定する

Stage6-Scenario5:
  Step1: 承認待ち操作を作る
  Step2: 承認期限が過ぎるまで待つ
  Step3: expired になり、危険操作が進まないことを判定する

Stage6-Scenario6:
  Step1: Input the instruction "Delete the file named test-output.txt."
  Step2: delete 実行前に承認待ちになることを判定する

Stage6-Scenario7:
  Step1: Input the instruction "Install an application or change system settings."
  Step2: installer または settings change の前に承認待ちになることを判定する

Stage6-Scenario8:
  Step1: Input the instruction "Open Calculator and read the visible result."
  Step2: 保存、送信、設定変更を含まないため承認待ちにならず進むことを判定する

Stage6-Scenario9:
  Step1: 危険な保存操作を承認待ちにする
  Step2: 承認しない
  Step3: 保存が実行されないことを判定する
  Step4: 未承認ブロックが確認できたらテスト成功
```

## Stage 7: メール通知

目的: メール通知が必要な状態変化で送信成功ログが残ること、宛先とレート制限が正しいことを保証します。E2Eでは外部メール送信を避けるため console delivery を使い、送信内容をコンソールへ出力します。

SMTP アカウント情報は Pi 5 側の以下から読みます。宛先は SMTP アカウント自身です。

```text
/home/nama/mail-send-vert.txt
```

| Scenario | ケース名 | 状態 | 目的 |
| --- | --- | --- | --- |
| Stage7-Scenario1 | `stage07_scenario01_completion_email_log` | implemented | 完了通知メールのSMTP成功ログ |
| Stage7-Scenario2 | `stage07_scenario02_emergency_email_log` | implemented | 非常停止メールのSMTP成功ログ |
| Stage7-Scenario3 | `stage07_scenario03_approval_request_email_log` | implemented | 承認要求メールのSMTP成功ログ |
| Stage7-Scenario4 | `stage07_scenario04_email_rate_limit` | implemented | 重複メールのレート制限 |
| Stage7-Scenario5 | `stage07_scenario05_email_self_recipient` | implemented | 宛先がSMTPアカウント自身であること |
| Stage7-Scenario6 | `stage07_scenario06_expected_failure_smtp_auth` | implemented | 期待失敗: SMTP認証失敗ログ |
| Stage7-Scenario7 | `stage07_scenario07_attachment_limit` | implemented | 添付スクリーンショット容量制限 |
| Stage7-Scenario8 | `stage07_scenario08_email_disabled_no_send` | implemented | email disabled 時の送信スキップ |

```text
Stage7-Scenario1:
  Step1: 短いブラウザ起動操作を完了させる
  Step2: 完了メールの SMTP 送信成功ログがあるか判定する

Stage7-Scenario2:
  Step1: 非常停止を発火する
  Step2: 非常停止メールの SMTP 送信成功ログがあるか判定する

Stage7-Scenario3:
  Step1: 承認待ち操作を作る
  Step2: 承認要求メールの SMTP 送信成功ログがあるか判定する

Stage7-Scenario4:
  Step1: 同じ通知対象イベントを短時間に複数回発生させる
  Step2: 重複通知が抑制またはレート制限されたことを判定する

Stage7-Scenario5:
  Step1: メール通知を1件送る
  Step2: 宛先が SMTP アカウント自身であることを通知ログから判定する

Stage7-Scenario6:
  Step1: テスト用の無効なSMTP認証情報で通知を送る
  Step2: SMTP authentication failure が notification_log に記録されることを判定する
  Step3: 送信失敗を安全に扱えたらテスト成功

Stage7-Scenario7:
  Step1: 添付上限より大きいスクリーンショット付き通知を発生させる
  Step2: resize、omit、reject のいずれかが設定に従って記録されるか判定する

Stage7-Scenario8:
  Step1: email.enabled = false で完了通知イベントを発生させる
  Step2: SMTP送信されず、skipped としてログされるか判定する
```

## Stage 8: 長時間操作

目的: 長時間プランの進捗、サスペンド/レジューム、画面差分確認、警告を保証します。

| Scenario | ケース名 | 状態 | 目的 |
| --- | --- | --- | --- |
| Stage8-Scenario1 | `stage08_scenario01_progress_display` | implemented | 進捗表示 |
| Stage8-Scenario2 | `stage08_scenario02_suspend_resume` | implemented | サスペンド/レジューム |
| Stage8-Scenario3 | `stage08_scenario03_screen_drift_requires_approval` | implemented | 画面差分が大きい場合の承認待ち |
| Stage8-Scenario4 | `stage08_scenario04_long_plan_warning` | implemented | 長時間操作警告 |
| Stage8-Scenario5 | `stage08_scenario05_cancel_long_plan` | implemented | 長時間プランのキャンセル |
| Stage8-Scenario6 | `stage08_scenario06_expected_failure_step_error` | implemented | 期待失敗: 長時間プラン中の失敗ステップ |
| Stage8-Scenario7 | `stage08_scenario07_resume_after_process_restart` | implemented | Pi側プロセス再起動後のresume状態 |

```text
Stage8-Scenario1:
  Step1: 長時間になる複数ステッププランを開始する
  Step2: completed/total、現在ステップ、残り見積もりが表示されているか判定する

Stage8-Scenario2:
  Step1: 長時間プランをサスペンドする
  Step2: レジューム時に再キャプチャーして保存状態から再開するか判定する

Stage8-Scenario3:
  Step1: サスペンド後に画面状態を大きく変える
  Step2: レジューム時に承認待ちまたは停止になるか判定する

Stage8-Scenario4:
  Step1: しきい値を超える長時間プランを作る
  Step2: 実行前に警告または承認待ちが表示されるか判定する

Stage8-Scenario5:
  Step1: 長時間プランを開始する
  Step2: cancel を実行する
  Step3: 進捗が止まり、以降のPC操作が発生しないことを判定する

Stage8-Scenario6:
  Step1: 長時間プランの途中に "DefinitelyNotARealApp12345" を開くステップを含める
  Step2: そのステップが failed になり、停止または介入待ちになることを判定する
  Step3: 失敗ステップを安全に扱えたらテスト成功

Stage8-Scenario7:
  Step1: 長時間プランをサスペンドする
  Step2: Pi側プロセスを再起動する
  Step3: suspend状態が復元され、画面検証なしに再開しないことを判定する
```

## Stage 9: トークン予算

目的: OpenAI API の使用量、予測量、予算超過時の停止または承認待ちを保証します。

| Scenario | ケース名 | 状態 | 目的 |
| --- | --- | --- | --- |
| Stage9-Scenario1 | `stage09_scenario01_operation_token_usage` | implemented | 操作単位の使用量表示 |
| Stage9-Scenario2 | `stage09_scenario02_plan_token_prediction` | implemented | プラン実行前の予測 |
| Stage9-Scenario3 | `stage09_scenario03_budget_exceeded_blocks` | implemented | 予算超過時の停止または承認待ち |
| Stage9-Scenario4 | `stage09_scenario04_daily_token_aggregate` | implemented | 1日合計の集計 |
| Stage9-Scenario5 | `stage09_scenario05_expected_failure_missing_usage` | implemented | 期待失敗: token usage 欠落 |
| Stage9-Scenario6 | `stage09_scenario06_daily_budget_reset` | implemented | 日次予算リセット |
| Stage9-Scenario7 | `stage09_scenario07_per_step_budget_warning` | implemented | step単位の予算警告 |

```text
Stage9-Scenario1:
  Step1: WebUI の token usage fixture で操作単位の使用量を記録する
  Step2: Logs view の SYSTEM LOG と TOKEN GRAPH があり、/api/logs/detail に token_usage が出るか判定する

Stage9-Scenario2:
  Step1: /api/tokens/predict で複数ステッププラン相当の予測を作る
  Step2: 実行前に /api/status の token_prediction に予測トークン量が表示されるか判定する

Stage9-Scenario3:
  Step1: /api/tokens/check-budget で設定上限を超える予測を作る
  Step2: token budget 理由で既存の approval pending フローに入ることを判定する

Stage9-Scenario4:
  Step1: 同じ日付に複数の token usage fixture を記録する
  Step2: /api/tokens?from=...&to=... の1日合計に反映されているか判定する

Stage9-Scenario5:
  Step1: /api/tokens/missing-usage-test で token usage metadata 欠落を扱う
  Step2: usage を 0 扱いせず、unknown 警告ログと estimated_tokens を残すか判定する
  Step3: 欠落を安全に扱えたらテスト成功

Stage9-Scenario6:
  Step1: UTC日次境界の前後に token usage fixture を記録する
  Step2: 日付範囲ごとの /api/tokens 集計がその日だけの使用量になるか判定する

Stage9-Scenario7:
  Step1: 小さい per-step token budget で /api/tokens/predict を実行する
  Step2: 実行前に /api/status の token_prediction に per-step 予算警告が表示されるか判定する
```

## Stage 10: Discord 連携

目的: Discord からの操作、通知、承認、非常停止が設定ファイルで許可された範囲だけで動くことを保証します。
Discord のコマンド仕様は `docs/DISCORD_COMMANDS.md` にまとめます。通常の bot mention は Planning request として扱い、
`hid:` prefix のみ直接 HID として扱います。

| Scenario | ケース名 | 状態 | 目的 |
| --- | --- | --- | --- |
| Stage10-Scenario1 | `stage10_scenario01_discord_screen_command` | implemented | `@AgentDev screen` |
| Stage10-Scenario2 | `stage10_scenario02_discord_request_command` | implemented | `@AgentDev request: ...` / default Planning |
| Stage10-Scenario3 | `stage10_scenario03_discord_stop_command` | implemented | `@AgentDev stop` |
| Stage10-Scenario4 | `stage10_scenario04_discord_approve_reject` | implemented | `@AgentDev approve` / `@AgentDev reject` |
| Stage10-Scenario5 | `stage10_scenario05_discord_unauthorized_ignored` | implemented | 許可外ギルド/チャンネル/ユーザーの拒否 |
| Stage10-Scenario6 | `stage10_scenario06_discord_attachment_limit` | implemented | Discord添付サイズ制限 |
| Stage10-Scenario7 | `stage10_scenario07_discord_rate_limit` | implemented | Discordコマンドのレート制限 |
| Stage10-Scenario8 | `stage10_scenario08_expected_failure_bot_offline` | implemented | 期待失敗: Discord bot offline |

```text
Stage10-Scenario1:
  Step1: 設定ファイルで許可されたギルド、チャンネル、ユーザーから @AgentDev screen を送る
  Step2: スクリーンショット要求が処理され、ログに残ることを判定する

Stage10-Scenario2:
  Step1: 許可された Discord から @AgentDev request: open browser でブラウザ起動を依頼する
  Step2: ブラウザが表示され、Discord 由来の操作としてログされることを判定する

Stage10-Scenario3:
  Step1: 許可された Discord から @AgentDev stop を送る
  Step2: 非常停止状態になり、Discord 由来としてログされることを判定する

Stage10-Scenario4:
  Step1: 承認待ち操作を作る
  Step2: Discord から @AgentDev approve または @AgentDev reject を送る
  Step3: 承認判断が反映され、ログされることを判定する

Stage10-Scenario5:
  Step1: 設定で許可されていないギルド、チャンネル、ユーザーからコマンドを送る
  Step2: コマンドが拒否または無視され、PC 操作が発生しないことを判定する

Stage10-Scenario6:
  Step1: 添付上限を超えるスクリーンショットで /screen を実行する
  Step2: resize、omit、too large のいずれかが設定通りに扱われるか判定する

Stage10-Scenario7:
  Step1: @AgentDev screen を設定されたレート制限より速く連続送信する
  Step2: throttle または queue され、PC操作が暴走しないことを判定する

Stage10-Scenario8:
  Step1: Discord bot 接続が無効な状態で Discord mode を起動する
  Step2: offline または connection failure が報告され、WebUI/CLI は利用可能なままか判定する
  Step3: 接続失敗を安全に扱えたらテスト成功
```

## 残る要確認事項

以下は、個別ステージ実装時に確定するとテストをさらに安定させられる項目です。

```text
Q-T007 承認待ちの期限切れ時間をテストでは何秒に短縮するか。
Q-T008 長時間操作の警告しきい値をテスト用に何ステップ、何秒、何トークンにするか。
Q-T009 Discord テスト用の project config ファイル名を config/local.toml 固定にするか、test config を別に置くか。
```
