# テスト実装計画

この文書は、Pico HID Bridge の本実装とは別に、TDD を回すためのテストプログラムを先に完成させる計画をまとめる。要求仕様と詳細仕様は `docs/PRODUCT_SPEC.md` に置き、この文書ではテスト実装の順序、成果物、完了条件だけを扱う。

関連文書:

```text
docs/TEST_SCENARIOS.md      開発ステップ別テストシナリオ台帳
docs/TEST_PROGRAM_SPEC.md   詳細テスト仕様書
docs/TESTING.md             実機テスト環境メモ
```

テスト環境:

```text
[開発マシン(Codex PC)] ==== Network === [Raspberry Pi5 (192.168.11.6)]
                                      [↑GPIO/UART] ===== Serial ===== [Raspberry Pi Pico] ==== USB === [PC]
                                      [↑USB Capture Board] ================ HDMI Cable =============== [↑ ] 
```

## 目的

TDD で本実装を進めるため、先に以下を満たすテスト基盤を完成させる。

```text
1. すべてのシナリオがテスト関数として存在する
2. 未実装機能のテストは skipped/pending ではなく、意味のある失敗になる
3. expected_failure 系は、期待した失敗を検出できれば成功になる
4. 実装ミスと実機環境差分を切り分けられる
5. 失敗時に artifacts から原因を追える
6. Unit / Integration / Hardware E2E を同じ命名規則で実行できる
```

## 基本方針

### pending の扱い

現在の `pi/pico_hid_bridge/e2e/cases.py` には `implemented = false` のケースがある。テスト実装完了後は、TDD 対象ケースについては `pending` で止めず、以下のいずれかにする。

```text
通常ケース:
  実行して、未実装機能が満たせないため fail する。

expected_failure ケース:
  操作失敗、拒否、未対応、到達不能、認証失敗などを検出できれば pass する。
  期待失敗を検出できない場合、または誤って成功扱いした場合は fail する。

環境未成立ケース:
  Pi5 / Pico / Capture / Target PC / OpenAI API などの前提がない場合は error ではなく
  infrastructure failure として分類する。
```

### テスト階層

```text
Unit
  ハードウェア不要。関数単体、設定、判定ロジック、バリデーションを検証する。

Integration
  Pi5 上のプロセス、Flask API、SQLite、設定ファイル、通知ログなどを検証する。
  原則として対象PC操作は行わない。

Hardware E2E
  Pi5 -> HDMI capture -> Computer Use API -> Pico UART -> 対象PC -> 再capture の全経路を使う。

Expected Failure E2E
  失敗することが正しいシナリオを実行し、失敗の検出と安全停止を検証する。
```

## 予定ディレクトリ

```text
tests/
├─ unit/
│  ├─ test_hid_commands.py
│  ├─ test_action_executor.py
│  ├─ test_config.py
│  ├─ test_e2e_model.py
│  ├─ test_expected_failure.py
│  └─ test_token_budget_rules.py
│
├─ integration/
│  ├─ test_pi_environment.py
│  ├─ test_webui_api.py
│  ├─ test_operation_log.py
│  ├─ test_email_notifications.py
│  └─ test_discord_config.py
│
├─ e2e/
│  ├─ test_stage01_core_io.py
│  ├─ test_stage02_operation_log.py
│  ├─ test_stage03_runtime_safety.py
│  ├─ test_stage04_webui_control.py
│  ├─ test_stage05_planning.py
│  ├─ test_stage06_approval.py
│  ├─ test_stage07_email_notification.py
│  ├─ test_stage08_long_running.py
│  ├─ test_stage09_token_budget.py
│  └─ test_stage10_discord.py
│
├─ helpers/
│  ├─ environment.py
│  ├─ remote.py
│  ├─ e2e_runner.py
│  ├─ artifacts.py
│  ├─ classification.py
│  └─ fixtures.py
│
└─ fixtures/
   ├─ config/
   ├─ db/
   ├─ openai/
   └─ notifications/
```

## 実装ステップ

### Step 1: テストメタモデル拡張

対象:

```text
pi/pico_hid_bridge/e2e/model.py
pi/pico_hid_bridge/e2e/cases.py
tests/helpers/classification.py
```

追加する主な項目:

```text
category                 normal | expected_failure | infrastructure | safety
expected_result          pass | fail_detected | blocked | rejected | unsupported | timeout
requires_hardware        true / false
requires_openai          true / false
requires_target_pc       true / false
requires_network         true / false
safe_to_run_by_default   true / false
failure_domain_hint      implementation | pi | pico | capture | target_pc | openai | external_service
```

完了条件:

```text
- 既存84シナリオすべてに category と expected_result が付く
- `python3 run_e2e_suite.py --list` で category と expected_result が見える
- pending ケースを runner が即終了しない
```

### Step 2: Unit テスト基盤

対象:

```text
tests/unit/
tests/helpers/
```

優先して作るテスト:

```text
- HID コマンド正規化と検証
- Computer Use action から HID コマンドへの変換
- expected_failure の成功/失敗判定
- E2E ケース定義の整合性
- config 読み込みと秘密値未混入
```

完了条件:

```text
- ローカルPCだけで unit test が実行できる
- Pi5、Pico、Capture、OpenAI API がなくても通る
- e2e_cases の全 action_task が ASCII であることを自動検査する
```

### Step 3: Pi5 Integration テスト基盤

対象:

```text
tests/integration/test_pi_environment.py
tests/integration/test_webui_api.py
tests/integration/test_operation_log.py
```

検証する前提:

```text
- SSH 接続
- /home/nama/openai-api-key.txt の存在
- /home/nama/mail-send-vert.txt の存在
- Python / pip / requirements
- /dev/video0 または設定された capture device
- /dev/serial0 または設定された UART device
- Flask /api/status
- runtime/test/ への書き込み
```

完了条件:

```text
- Pi5 接続失敗と実装失敗を別のエラー分類で出せる
- 対象PCを操作しない integration test が実行できる
- artifact に remote command, stdout, stderr, exit_code が残る
```

### Step 4: Hardware Preflight

対象:

```text
tests/integration/test_pi_environment.py
tests/helpers/environment.py
```

順番:

```text
1. SSH 接続
2. Pi5 の Python 実行
3. OpenAI API key file 確認
4. SMTP account file 確認
5. Capture device 確認
6. 1枚キャプチャして非空画像か確認
7. UART device 確認
8. Pico HID に安全なキーを送信できるか確認
9. 対象PC画面が capture に映っているか確認
```

完了条件:

```text
- Hardware E2E の前に preflight を必ず実行できる
- preflight が失敗した場合、E2E 本体を実行しない
- 失敗分類が Pi5 / Pico / Capture / Target PC / OpenAI に分かれる
```

### Step 5: E2E runner 強化

対象:

```text
pi/pico_hid_bridge/e2e/runner.py
pi/tools/run_e2e_case.py
pi/tools/run_e2e_suite.py
tests/helpers/e2e_runner.py
```

追加する機能:

```text
- JSON result 出力
- expected_failure 判定
- artifacts index
- step ごとの prompt / response / actions 保存
- environment preflight 結果の保存
- category / stage / scenario フィルタ
- infrastructure failure と assertion failure の分離
```

完了条件:

```text
- 84シナリオすべてがテスト関数から runner を呼べる
- 未実装通常ケースは fail になる
- expected_failure ケースは期待失敗を検出できれば pass になる
- 失敗時に result.json だけで大分類を判断できる
```

### Step 6: Stage 別 E2E テスト関数実装

現状メモ: 現在のリポジトリでは、stage 別ファイルではなく `tests/e2e/test_scenarios.py` が `pi/pico_hid_bridge/e2e/cases.py` のケース定義からテスト関数を動的生成する。TDD でケースを追加する場合はこの現状を優先し、stage 別ファイルへの分割は別タスクとして明示されるまで行わない。`pi/e2e_cases.py` は既存import互換のラッパーであり、ケース実体は追加しない。

対象:

```text
tests/e2e/test_stage01_core_io.py
...
tests/e2e/test_stage10_discord.py
```

方針:

```text
- 各シナリオ名と同じ関数名にする
- 関数内では個別ロジックを書かず、共通 helper に scenario name を渡す
- 例外的な fixture だけ関数引数で受ける
```

完了条件:

```text
- `pytest tests/e2e --collect-only` で84本すべて見える
- シナリオ台帳とテスト関数の差分を検出する unit test がある
```

### Step 7: PowerShell 入口整理

PowerShell 入口:

```text
scripts/ps1/test_unit.ps1
scripts/ps1/test_integration.ps1
scripts/ps1/test_e2e_pytest.ps1
scripts/ps1/test_pytest_call_only_on_pi.ps1
scripts/ps1/test_e2e_suite.ps1
scripts/ps1/test_all.ps1
```

現状メモ: PowerShell ラッパーは root 直下ではなく `scripts/ps1/` に置く。独立した `test_preflight.ps1` は置かず、preflight は `scripts/ps1/test_integration.ps1` の対象 `tests/preflight` として実行する。

完了条件:

```text
- Windows 側から用途別に実行できる
- SSH key は id_rsa を使う
- Pi5 へコピーする対象が明確
- 戻り値で CI 的に成功/失敗を判断できる
```

### Step 8: ドキュメント更新

更新対象:

```text
docs/TESTING.md
docs/TEST_SCENARIOS.md
docs/TEST_PROGRAM_SPEC.md
AGENT.md
```

完了条件:

```text
- 新しい実行方法が docs/TESTING.md に載る
- TDD で新機能に入る前にどのテストを赤にするか分かる
- 失敗時の切り分け手順が docs/TEST_PROGRAM_SPEC.md に載る
```

## TDD 運用ループ

```text
1. 実装対象 Stage / Scenario を選ぶ
2. 対応する unit / integration / e2e test を確認する
3. テストを実行して赤を確認する
4. 最小実装を行う
5. unit test を緑にする
6. integration test を緑にする
7. hardware preflight を通す
8. 対応 E2E を緑にする
9. 既存 Stage の回帰テストを実行する
10. ドキュメントとテスト結果を更新する
```

## 優先順位

```text
P0:
  Unit 基盤、ケース整合性検査、Pi5 preflight、Stage1 E2E

P1:
  Stage2-4 の integration / E2E

P2:
  Stage5 planning、Stage6 approval、Stage7 email

P3:
  Stage8 long-running、Stage9 token、Stage10 Discord
```

## 完了定義

テスト実装フェーズの完了は、以下すべてを満たすこと。

```text
- 84シナリオすべてにテスト関数がある
- Unit / Integration / E2E の実行入口がある
- Pi5 preflight がある
- expected_failure の扱いが実装されている
- result.json と artifacts が保存される
- 失敗時の切り分け手順が文書化されている
- Pi5 上で --list と preflight が通る
- 少なくとも Stage1-Scenario1 がフルE2Eで通る
```
