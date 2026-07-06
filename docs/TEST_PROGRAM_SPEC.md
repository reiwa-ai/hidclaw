# 詳細テスト仕様書

この文書は、TDD で使用するテストプログラムの詳細仕様を定義する。プロジェクト本体の要求仕様ではなく、テストコード、テスト関数、実行条件、失敗切り分け、成果物の仕様だけを扱う。

関連文書:

```text
docs/TEST_IMPLEMENTATION_PLAN.md  テスト実装計画
docs/TEST_SCENARIOS.md            テストシナリオ台帳
docs/TESTING.md                   実機テスト環境メモ
```

## 1. テスト分類

```text
unit
  ローカルPCのみで実行できる。ハードウェア、Pi5、OpenAI API を使わない。

integration
  Pi5、Flask、SQLite、設定、通知ログなどを検証する。原則として対象PCを操作しない。

preflight
  Hardware E2E の実行前提を確認する。失敗した場合 E2E 本体を実行しない。

e2e
  Pi5、HDMI capture、Computer Use API、Pico UART、対象PCを使う。

expected_failure
  操作の失敗、拒否、未対応、到達不能、認証失敗などを検出できたら成功とする。
```

## 2. 実行環境

### 2.1 Windows 側

```text
workspace: C:\Users\sakam\Documents\Work\AgentDev
shell:     PowerShell
ssh key:   id_rsa
```

予定スクリプト:

```powershell
.\scripts\ps1\test_unit.ps1
.\scripts\ps1\test_integration.ps1
.\scripts\ps1\test_e2e_suite.ps1 -Stage stage01_core_io
.\scripts\ps1\test_all.ps1
```

現状では独立した `test_preflight.ps1` は置かず、preflight は `scripts/ps1/test_integration.ps1` が `tests/preflight` として一緒に実行する。独立スクリプトを追加するまでは、Codex は `test_preflight.ps1` を新規前提にしない。

### 2.2 Pi5 側

```text
host: 192.168.11.6
user: nama
key:  id_rsa
repo copy: /home/nama/pi
OpenAI API key: /home/nama/openai-api-key.txt
SMTP account:   /home/nama/mail-send-vert.txt
UART:           /dev/serial0
capture:        /dev/video0
runtime:        /home/nama/pi/runtime/test
artifacts:      /home/nama/pi/captures
```

### 2.3 操作対象PC

```text
- Pico が USB HID keyboard/mouse として接続されている
- HDMI 出力がキャプチャーボード経由で Pi5 から見える
- テスト開始前に ALT+F4 と N で既存ウィンドウを閉じられる
- 日本語IME入力を前提にしない
- テストで入力する文字列は ASCII English のみ
```

## 3. 共通データ構造

### 3.1 TestEnvironment

予定ファイル:

```text
tests/helpers/environment.py
```

予定定義:

```python
from dataclasses import dataclass
from pathlib import Path

@dataclass(frozen=True)
class TestEnvironment:
    pi_host: str
    pi_user: str
    ssh_key: Path
    remote_pi_dir: str
    openai_api_key_file: str
    smtp_account_file: str
    capture_device: str
    uart_port: str
    webui_host: str
    webui_port: int
    runtime_dir: str
    artifacts_dir: str
    target_pc_os: str
```

既定値:

```text
pi_host=192.168.11.6
pi_user=nama
ssh_key=id_rsa
remote_pi_dir=/home/nama/pi
openai_api_key_file=/home/nama/openai-api-key.txt
smtp_account_file=/home/nama/mail-send-vert.txt
capture_device=/dev/video0
uart_port=/dev/serial0
webui_host=192.168.11.6
webui_port=18080
runtime_dir=/home/nama/pi/runtime/test
artifacts_dir=/home/nama/pi/captures
target_pc_os=windows
```

### 3.2 TestResult

予定ファイル:

```text
tests/helpers/artifacts.py
```

予定定義:

```python
@dataclass(frozen=True)
class TestResult:
    case_name: str
    stage: str
    status: str
    expected_result: str
    failure_domain: str | None
    exit_code: int
    artifacts_dir: str
    result_json: str
    message: str
```

`status`:

```text
pass
fail
expected_failure_detected
infrastructure_failure
error
skipped_by_filter
```

`failure_domain`:

```text
implementation
pi_ssh
pi_dependency
pi_process
pico_uart
capture_board
target_pc_state
openai_api
smtp
discord
test_spec
unknown
```

## 4. 共通ヘルパー関数仕様

### 4.1 remote.py

```python
def run_local(
    args: list[str],
    *,
    cwd: Path,
    timeout_sec: int = 60,
) -> CommandResult:
    ...
```

用途:

```text
PowerShell ではなく Python テスト内からローカルコマンドを実行する。
```

```python
def run_ssh(
    env: TestEnvironment,
    command: str,
    *,
    timeout_sec: int = 60,
) -> CommandResult:
    ...
```

用途:

```text
Pi5 上でコマンドを実行する。
stdout, stderr, exit_code, elapsed_sec を artifacts に残す。
```

```python
def copy_pi_sources(
    env: TestEnvironment,
    *,
    source_dir: Path = Path("pi"),
    timeout_sec: int = 120,
) -> CommandResult:
    ...
```

用途:

```text
Windows 側 workspace の pi/ を Pi5 の /home/nama/pi へコピーする。
```

### 4.2 environment.py

```python
def load_test_environment(
    *,
    pi_host: str = "192.168.11.6",
    pi_user: str = "nama",
    ssh_key: Path = Path("id_rsa"),
    webui_port: int = 18080,
) -> TestEnvironment:
    ...
```

```python
def check_pi_ssh(env: TestEnvironment) -> CheckResult:
    ...
```

期待:

```text
ssh hostname が成功し、RaspberryPi または設定済み hostname を返す。
```

```python
def check_pi_required_files(env: TestEnvironment) -> CheckResult:
    ...
```

確認対象:

```text
/home/nama/openai-api-key.txt
/home/nama/mail-send-vert.txt
/home/nama/pi
```

```python
def check_pi_devices(env: TestEnvironment) -> CheckResult:
    ...
```

確認対象:

```text
/dev/video0
/dev/serial0
```

```python
def check_capture_smoke(env: TestEnvironment, *, output_name: str = "preflight_capture.png") -> CheckResult:
    ...
```

期待:

```text
キャプチャー画像を1枚保存し、ファイルサイズ、解像度、平均輝度が閾値以上。
```

```python
def check_pico_uart_smoke(env: TestEnvironment) -> CheckResult:
    ...
```

期待:

```text
Pico UART へ `PING` を送信し、対象PCへ HID 入力を送らずに ACK が返ることを確認する。
ACK timeout は unit test で `TimeoutError` として固定する。
```

```python
def check_openai_key(env: TestEnvironment) -> CheckResult:
    ...
```

期待:

```text
API key file が存在し、空でない。
実API呼び出しは preflight の軽量モードでは行わない。
```

```python
def run_hardware_preflight(env: TestEnvironment) -> PreflightResult:
    ...
```

順序:

```text
1. SSH
2. source copy
3. dependencies
4. required files
5. devices
6. capture smoke
7. UART smoke
8. OpenAI key file
9. target screen readable
```

### 4.3 e2e_runner.py

```python
def list_e2e_cases(
    *,
    stage: str | None = None,
    category: str | None = None,
    include_expected_failure: bool = True,
) -> list[E2ETestCase]:
    ...
```

```python
def run_e2e_case_by_name(
    env: TestEnvironment,
    case_name: str,
    *,
    api_key_file: str | None = None,
    output_root: str | None = None,
    pre_test_close_attempts: int = 8,
    pre_test_close_delay: float = 0.5,
    max_action_turns: int = 5,
    max_verify_turns: int = 5,
    api_timeout: float = 60.0,
    expected_failure: bool | None = None,
    require_preflight: bool = True,
) -> TestResult:
    ...
```

対応:

```text
pi/run_e2e_case.py <case_name>
pi/pico_hid_bridge/e2e/runner.py::run_case
```

```python
def assert_e2e_passed(result: TestResult) -> None:
    ...
```

通常ケース:

```text
status == pass
```

expected_failure ケース:

```text
status == expected_failure_detected
```

```python
def classify_e2e_failure(result: TestResult) -> str:
    ...
```

分類:

```text
implementation / pi_ssh / pi_dependency / pico_uart / capture_board /
target_pc_state / openai_api / smtp / discord / test_spec / unknown
```

### 4.4 artifacts.py

```python
def create_artifact_dir(
    *,
    root: Path,
    case_name: str,
    timestamp: str | None = None,
) -> Path:
    ...
```

```python
def write_result_json(
    result: TestResult,
    *,
    path: Path,
) -> None:
    ...
```

```python
def collect_remote_artifacts(
    env: TestEnvironment,
    remote_artifacts_dir: str,
    local_artifacts_dir: Path,
) -> None:
    ...
```

保存するもの:

```text
result.json
result.txt
preflight.json
remote_commands.jsonl
step*_before.png
step*_after.png
openai_requests.jsonl
openai_responses.jsonl
hid_commands.jsonl
stdout.txt
stderr.txt
```

## 5. Unit テスト関数仕様

### 5.1 tests/unit/test_hid_commands.py

```python
def test_normalize_plain_text_command() -> None: ...
def test_normalize_key_win_r() -> None: ...
def test_normalize_key_alt_f4() -> None: ...
def test_normalize_key_n() -> None: ...
def test_validate_rejects_modifier_without_normal_key() -> None: ...
def test_validate_rejects_too_long_text() -> None: ...
def test_validate_rejects_non_ascii_text() -> None: ...
```

対応シナリオ:

```text
stage01_scenario02_run_dialog_shortcut
stage01_scenario03_text_editor_input
stage04_scenario05_expected_failure_invalid_hid_command
```

### 5.2 tests/unit/test_action_executor.py

```python
def test_execute_type_action_sends_text(fake_transport: FakeTransport) -> None: ...
def test_execute_keypress_action_sends_key_combo(fake_transport: FakeTransport) -> None: ...
def test_execute_wait_action_waits(fake_sleep: FakeSleep) -> None: ...
def test_execute_unsupported_action_reports_event(fake_transport: FakeTransport) -> None: ...
```

対応シナリオ:

```text
stage01_scenario01_open_browser
stage01_scenario06_expected_failure_unsupported_drag
stage05_scenario13_expected_failure_paint_freehand
```

### 5.3 tests/unit/test_e2e_case_definitions.py

```python
def test_all_case_names_are_unique() -> None: ...
def test_all_case_names_have_test_functions() -> None: ...
def test_all_action_tasks_are_ascii() -> None: ...
def test_expected_failure_cases_have_expected_failure_in_name_or_category() -> None: ...
def test_all_cases_have_stage_description_and_steps() -> None: ...
```

対応シナリオ:

```text
all 84 scenarios
```

### 5.4 tests/unit/test_expected_failure.py

```python
def test_expected_failure_passes_when_failure_detected() -> None: ...
def test_expected_failure_fails_when_operation_succeeds() -> None: ...
def test_normal_case_fails_when_verification_false() -> None: ...
def test_infrastructure_failure_is_not_counted_as_expected_failure() -> None: ...
```

対応シナリオ:

```text
all scenarios containing expected_failure
```

### 5.5 tests/unit/test_config.py

```python
def test_example_config_has_no_secret_values() -> None: ...
def test_email_config_defaults_disabled() -> None: ...
def test_discord_config_defaults_disabled() -> None: ...
def test_storage_limit_config_is_present() -> None: ...
def test_runtime_dir_can_be_overridden_for_tests() -> None: ...
```

対応シナリオ:

```text
stage02_scenario04_storage_limit
stage07_scenario08_email_disabled_no_send
stage10_scenario05_discord_unauthorized_ignored
```

## 6. Integration テスト関数仕様

### 6.1 tests/integration/test_pi_environment.py

```python
def test_pi_ssh_connects(env: TestEnvironment) -> None: ...
def test_pi_required_files_exist(env: TestEnvironment) -> None: ...
def test_pi_python_dependencies(env: TestEnvironment) -> None: ...
def test_pi_capture_device_exists(env: TestEnvironment) -> None: ...
def test_pi_uart_device_exists(env: TestEnvironment) -> None: ...
def test_pi_capture_smoke(env: TestEnvironment) -> None: ...
def test_pi_pico_uart_smoke(env: TestEnvironment) -> None: ...
```

実行条件:

```text
Pi5 reachable
id_rsa usable
pi/ copied to /home/nama/pi
```

### 6.2 tests/integration/test_webui_api.py

```python
def test_webui_status_api(env: TestEnvironment) -> None: ...
def test_webui_manual_hid_rejects_invalid_hid(env: TestEnvironment) -> None: ...
def test_webui_emergency_stop_state(env: TestEnvironment) -> None: ...
def test_webui_planning_toggle(env: TestEnvironment) -> None: ...
def test_webui_screenshot_api(env: TestEnvironment) -> None: ...
```

対応シナリオ:

```text
stage04_scenario01_lan_webui_status
stage04_scenario03_planning_toggle
stage04_scenario05_expected_failure_invalid_hid_command
stage04_scenario06_webui_emergency_button
stage04_scenario07_refresh_screenshot
```

### 6.3 tests/integration/test_operation_log.py

```python
def test_user_input_log_insert_and_query(env: TestEnvironment) -> None: ...
def test_operation_log_insert_and_query(env: TestEnvironment) -> None: ...
def test_screenshot_log_insert_and_query(env: TestEnvironment) -> None: ...
def test_error_log_insert_and_query(env: TestEnvironment) -> None: ...
def test_log_storage_limit_rotation(env: TestEnvironment) -> None: ...
def test_corrupt_database_recovery(env: TestEnvironment) -> None: ...
```

対応シナリオ:

```text
stage02_scenario01_user_input_log
stage02_scenario02_operation_log
stage02_scenario03_screenshot_log
stage02_scenario04_storage_limit
stage02_scenario05_error_log
stage02_scenario06_log_query_filters
stage02_scenario07_expected_failure_corrupt_db_recovery
```

### 6.4 tests/integration/test_email_notifications.py

```python
def test_smtp_account_file_parse(env: TestEnvironment) -> None: ...
def test_completion_email_success_log(env: TestEnvironment) -> None: ...
def test_emergency_email_success_log(env: TestEnvironment) -> None: ...
def test_approval_email_success_log(env: TestEnvironment) -> None: ...
def test_email_rate_limit(env: TestEnvironment) -> None: ...
def test_email_self_recipient(env: TestEnvironment) -> None: ...
def test_smtp_auth_failure_log(env: TestEnvironment) -> None: ...
def test_email_disabled_no_send(env: TestEnvironment) -> None: ...
```

対応シナリオ:

```text
stage07_scenario01_completion_email_log
stage07_scenario02_emergency_email_log
stage07_scenario03_approval_request_email_log
stage07_scenario04_email_rate_limit
stage07_scenario05_email_self_recipient
stage07_scenario06_expected_failure_smtp_auth
stage07_scenario08_email_disabled_no_send
```

### 6.5 tests/integration/test_discord_config.py

```python
def test_discord_config_loads_allowed_scope(env: TestEnvironment) -> None: ...
def test_discord_rejects_unauthorized_source(env: TestEnvironment) -> None: ...
def test_discord_rate_limit_rules(env: TestEnvironment) -> None: ...
def test_discord_offline_failure_classification(env: TestEnvironment) -> None: ...
```

対応シナリオ:

```text
stage10_scenario05_discord_unauthorized_ignored
stage10_scenario07_discord_rate_limit
stage10_scenario08_expected_failure_bot_offline
```

## 7. E2E テスト関数仕様

E2E テスト関数は、個別ロジックを持たず、シナリオ名を `run_e2e_case_by_name()` に渡す。

現状の実装では、E2E テスト関数は stage 別ファイルではなく `tests/e2e/test_scenarios.py` で `pi/pico_hid_bridge/e2e/cases.py` のケース定義から動的に生成する。TDD で新しい E2E ケースを追加するときは、まず `pi/pico_hid_bridge/e2e/cases.py` と既存の動的生成テストを更新し、stage 別テストファイルの新設は明示的な設計変更がある場合だけ行う。`pi/e2e_cases.py` は互換ラッパーであり、ケース実体は置かない。

共通形:

```python
def test_<scenario_name>(env: TestEnvironment) -> None:
    result = run_e2e_case_by_name(env, "<scenario_name>")
    assert_e2e_passed(result)
```

expected_failure の共通形:

```python
def test_<scenario_name>(env: TestEnvironment) -> None:
    result = run_e2e_case_by_name(env, "<scenario_name>", expected_failure=True)
    assert_e2e_passed(result)
```

### 7.1 Stage 1

| 関数名 | 対応シナリオ |
| --- | --- |
| `test_stage01_scenario01_open_browser(env)` | `stage01_scenario01_open_browser` |
| `test_stage01_scenario02_run_dialog_shortcut(env)` | `stage01_scenario02_run_dialog_shortcut` |
| `test_stage01_scenario03_text_editor_input(env)` | `stage01_scenario03_text_editor_input` |
| `test_stage01_scenario04_calculator_basic(env)` | `stage01_scenario04_calculator_basic` |
| `test_stage01_scenario05_paint_text(env)` | `stage01_scenario05_paint_text` |
| `test_stage01_scenario06_expected_failure_unsupported_drag(env)` | `stage01_scenario06_expected_failure_unsupported_drag` |
| `test_stage01_scenario07_expected_failure_nonexistent_app(env)` | `stage01_scenario07_expected_failure_nonexistent_app` |

### 7.2 Stage 2

| 関数名 | 対応シナリオ |
| --- | --- |
| `test_stage02_scenario01_user_input_log(env)` | `stage02_scenario01_user_input_log` |
| `test_stage02_scenario02_operation_log(env)` | `stage02_scenario02_operation_log` |
| `test_stage02_scenario03_screenshot_log(env)` | `stage02_scenario03_screenshot_log` |
| `test_stage02_scenario04_storage_limit(env)` | `stage02_scenario04_storage_limit` |
| `test_stage02_scenario05_error_log(env)` | `stage02_scenario05_error_log` |
| `test_stage02_scenario06_log_query_filters(env)` | `stage02_scenario06_log_query_filters` |
| `test_stage02_scenario07_expected_failure_corrupt_db_recovery(env)` | `stage02_scenario07_expected_failure_corrupt_db_recovery` |

### 7.3 Stage 3

| 関数名 | 対応シナリオ |
| --- | --- |
| `test_stage03_scenario01_emergency_stop_blocks_hid(env)` | `stage03_scenario01_emergency_stop_blocks_hid` |
| `test_stage03_scenario02_new_command_resets_state(env)` | `stage03_scenario02_new_command_resets_state` |
| `test_stage03_scenario03_suspend_resume_state(env)` | `stage03_scenario03_suspend_resume_state` |
| `test_stage03_scenario04_stop_cancels_pending_approval(env)` | `stage03_scenario04_stop_cancels_pending_approval` |

### 7.4 Stage 4

| 関数名 | 対応シナリオ |
| --- | --- |
| `test_stage04_scenario01_lan_webui_status(env)` | `stage04_scenario01_lan_webui_status` |
| `test_stage04_scenario02_manual_hid_command(env)` | `stage04_scenario02_manual_hid_command` |
| `test_stage04_scenario03_planning_toggle(env)` | `stage04_scenario03_planning_toggle` |
| `test_stage04_scenario04_log_panes(env)` | `stage04_scenario04_log_panes` |
| `test_stage04_scenario05_expected_failure_invalid_hid_command(env)` | `stage04_scenario05_expected_failure_invalid_hid_command` |
| `test_stage04_scenario06_webui_emergency_button(env)` | `stage04_scenario06_webui_emergency_button` |
| `test_stage04_scenario07_refresh_screenshot(env)` | `stage04_scenario07_refresh_screenshot` |
| `test_stage04_scenario08_webui_request_open_browser(env)` | `stage04_scenario08_webui_request_open_browser` |
| `test_stage04_scenario09_webui_request_run_dialog(env)` | `stage04_scenario09_webui_request_run_dialog` |
| `test_stage04_scenario10_webui_request_text_editor_input(env)` | `stage04_scenario10_webui_request_text_editor_input` |
| `test_stage04_scenario11_webui_request_calculator_basic(env)` | `stage04_scenario11_webui_request_calculator_basic` |
| `test_stage04_scenario12_webui_request_paint_text(env)` | `stage04_scenario12_webui_request_paint_text` |
| `test_stage04_scenario13_webui_request_expected_failure_unsupported_drag(env)` | `stage04_scenario13_webui_request_expected_failure_unsupported_drag` |
| `test_stage04_scenario14_webui_request_expected_failure_nonexistent_app(env)` | `stage04_scenario14_webui_request_expected_failure_nonexistent_app` |

### 7.5 Stage 5

| 関数名 | 対応シナリオ |
| --- | --- |
| `test_stage05_scenario01_default_web_raspberry_pi_pico(env)` | `stage05_scenario01_default_web_raspberry_pi_pico` |
| `test_stage05_scenario02_google_http_status_codes(env)` | `stage05_scenario02_google_http_status_codes` |
| `test_stage05_scenario03_wikipedia_ada_lovelace(env)` | `stage05_scenario03_wikipedia_ada_lovelace` |
| `test_stage05_scenario04_arxiv_attention_paper(env)` | `stage05_scenario04_arxiv_attention_paper` |
| `test_stage05_scenario05_planning_disabled_single_step(env)` | `stage05_scenario05_planning_disabled_single_step` |
| `test_stage05_scenario06_calculator_plan(env)` | `stage05_scenario06_calculator_plan` |
| `test_stage05_scenario07_paint_text_plan(env)` | `stage05_scenario07_paint_text_plan` |
| `test_stage05_scenario08_calculator_to_editor(env)` | `stage05_scenario08_calculator_to_editor` |
| `test_stage05_scenario09_browser_to_paint_label(env)` | `stage05_scenario09_browser_to_paint_label` |
| `test_stage05_scenario10_expected_failure_unreachable_url(env)` | `stage05_scenario10_expected_failure_unreachable_url` |
| `test_stage05_scenario11_expected_failure_missing_app(env)` | `stage05_scenario11_expected_failure_missing_app` |
| `test_stage05_scenario12_expected_failure_calculator_divide_by_zero(env)` | `stage05_scenario12_expected_failure_calculator_divide_by_zero` |
| `test_stage05_scenario13_expected_failure_paint_freehand(env)` | `stage05_scenario13_expected_failure_paint_freehand` |

### 7.6 Stage 6

| 関数名 | 対応シナリオ |
| --- | --- |
| `test_stage06_scenario01_file_save_requires_approval(env)` | `stage06_scenario01_file_save_requires_approval` |
| `test_stage06_scenario02_send_or_post_requires_approval(env)` | `stage06_scenario02_send_or_post_requires_approval` |
| `test_stage06_scenario03_login_requires_approval(env)` | `stage06_scenario03_login_requires_approval` |
| `test_stage06_scenario04_reject_prevents_execution(env)` | `stage06_scenario04_reject_prevents_execution` |
| `test_stage06_scenario05_approval_timeout(env)` | `stage06_scenario05_approval_timeout` |
| `test_stage06_scenario06_delete_requires_approval(env)` | `stage06_scenario06_delete_requires_approval` |
| `test_stage06_scenario07_install_requires_approval(env)` | `stage06_scenario07_install_requires_approval` |
| `test_stage06_scenario08_safe_read_no_approval(env)` | `stage06_scenario08_safe_read_no_approval` |
| `test_stage06_scenario09_expected_failure_unapproved_action(env)` | `stage06_scenario09_expected_failure_unapproved_action` |

### 7.7 Stage 7

| 関数名 | 対応シナリオ |
| --- | --- |
| `test_stage07_scenario01_completion_email_log(env)` | `stage07_scenario01_completion_email_log` |
| `test_stage07_scenario02_emergency_email_log(env)` | `stage07_scenario02_emergency_email_log` |
| `test_stage07_scenario03_approval_request_email_log(env)` | `stage07_scenario03_approval_request_email_log` |
| `test_stage07_scenario04_email_rate_limit(env)` | `stage07_scenario04_email_rate_limit` |
| `test_stage07_scenario05_email_self_recipient(env)` | `stage07_scenario05_email_self_recipient` |
| `test_stage07_scenario06_expected_failure_smtp_auth(env)` | `stage07_scenario06_expected_failure_smtp_auth` |
| `test_stage07_scenario07_attachment_limit(env)` | `stage07_scenario07_attachment_limit` |
| `test_stage07_scenario08_email_disabled_no_send(env)` | `stage07_scenario08_email_disabled_no_send` |

### 7.8 Stage 8

| 関数名 | 対応シナリオ |
| --- | --- |
| `test_stage08_scenario01_progress_display(env)` | `stage08_scenario01_progress_display` |
| `test_stage08_scenario02_suspend_resume(env)` | `stage08_scenario02_suspend_resume` |
| `test_stage08_scenario03_screen_drift_requires_approval(env)` | `stage08_scenario03_screen_drift_requires_approval` |
| `test_stage08_scenario04_long_plan_warning(env)` | `stage08_scenario04_long_plan_warning` |
| `test_stage08_scenario05_cancel_long_plan(env)` | `stage08_scenario05_cancel_long_plan` |
| `test_stage08_scenario06_expected_failure_step_error(env)` | `stage08_scenario06_expected_failure_step_error` |
| `test_stage08_scenario07_resume_after_process_restart(env)` | `stage08_scenario07_resume_after_process_restart` |

### 7.9 Stage 9

| 関数名 | 対応シナリオ |
| --- | --- |
| `test_stage09_scenario01_operation_token_usage(env)` | `stage09_scenario01_operation_token_usage` |
| `test_stage09_scenario02_plan_token_prediction(env)` | `stage09_scenario02_plan_token_prediction` |
| `test_stage09_scenario03_budget_exceeded_blocks(env)` | `stage09_scenario03_budget_exceeded_blocks` |
| `test_stage09_scenario04_daily_token_aggregate(env)` | `stage09_scenario04_daily_token_aggregate` |
| `test_stage09_scenario05_expected_failure_missing_usage(env)` | `stage09_scenario05_expected_failure_missing_usage` |
| `test_stage09_scenario06_daily_budget_reset(env)` | `stage09_scenario06_daily_budget_reset` |
| `test_stage09_scenario07_per_step_budget_warning(env)` | `stage09_scenario07_per_step_budget_warning` |

### 7.10 Stage 10

| 関数名 | 対応シナリオ |
| --- | --- |
| `test_stage10_scenario01_discord_screen_command(env)` | `stage10_scenario01_discord_screen_command` |
| `test_stage10_scenario02_discord_request_command(env)` | `stage10_scenario02_discord_request_command` |
| `test_stage10_scenario03_discord_stop_command(env)` | `stage10_scenario03_discord_stop_command` |
| `test_stage10_scenario04_discord_approve_reject(env)` | `stage10_scenario04_discord_approve_reject` |
| `test_stage10_scenario05_discord_unauthorized_ignored(env)` | `stage10_scenario05_discord_unauthorized_ignored` |
| `test_stage10_scenario06_discord_attachment_limit(env)` | `stage10_scenario06_discord_attachment_limit` |
| `test_stage10_scenario07_discord_rate_limit(env)` | `stage10_scenario07_discord_rate_limit` |
| `test_stage10_scenario08_expected_failure_bot_offline(env)` | `stage10_scenario08_expected_failure_bot_offline` |

## 8. 実行条件

### 8.1 Unit

```text
- Windows 側 workspace にいる
- Python が使える
- Pi5、Pico、Capture、OpenAI API は不要
- 外部ネットワーク不要
```

### 8.2 Integration

```text
- Pi5 へ SSH できる
- id_rsa が使える
- Pi5 上に /home/nama/pi を配置できる
- Flask / SQLite / config / runtime/test を使える
- 対象PC操作は原則不要
```

### 8.3 Hardware E2E

```text
- Pi5: 192.168.11.6 に接続されている
- Pi5 SSH: id_rsa で nama ユーザーへログインできる
- Pi5 -> Pico: /dev/serial0 が使える
- Pico -> 対象PC: USB HID keyboard/mouse として認識されている
- 対象PC -> Pi5: HDMI capture で画面が /dev/video0 に映る
- OpenAI API key: /home/nama/openai-api-key.txt にある
- テスト開始前に ALT+F4 / N のクリーンアップが許容される
- 対象PC画面に秘密情報が表示されていない
```

### 8.4 Email

```text
- /home/nama/mail-send-vert.txt が存在する
- SMTP アカウント自身へ送信する
- 実受信確認ではなく SMTP 送信成功ログを合格条件にする
```

### 8.5 Discord

```text
- Discord は最後に実装する
- guild/channel/user/role は設定ファイルで指定する
- テスト時には project config を使う
- bot token はリポジトリに保存しない
```

## 9. 失敗時の切り分け

### 9.1 最初に見るもの

```text
1. result.json
2. preflight.json
3. result.txt
4. step*_before.png / step*_after.png
5. remote_commands.jsonl
6. hid_commands.jsonl
7. openai_responses.jsonl
```

### 9.2 判定フロー

```text
preflight が失敗している:
  実装ミスではなく環境または接続の問題として扱う。

preflight は成功、unit/integration が失敗:
  本実装またはテスト仕様の問題として扱う。

preflight は成功、E2E の capture before が黒画面/無信号:
  capture_board または対象PC映像出力の問題として扱う。

capture は正常、HID操作後に画面が変わらない:
  Pico UART、Pico firmware、対象PC USB HID認識、または対象PC focus の問題として扱う。

HID操作は効くが Computer Use が未対応 action を返す:
  本実装の action mapping 不足、またはシナリオの難易度問題として扱う。

OpenAI API が 401/403/429/5xx:
  openai_api 問題として扱う。実装判断に使わない。

expected_failure ケースで操作が成功した:
  安全制御の実装ミスとして扱う。

expected_failure ケースで環境エラーになった:
  expected failure 成功にはしない。infrastructure_failure として扱う。
```

### 9.3 具体的な確認手順

SSH:

```powershell
ssh.exe -i id_rsa -l nama 192.168.11.6 hostname
```

Pi5 ファイル:

```powershell
ssh.exe -i id_rsa -l nama 192.168.11.6 "test -f /home/nama/openai-api-key.txt; echo openai_key=$?"
ssh.exe -i id_rsa -l nama 192.168.11.6 "test -f /home/nama/mail-send-vert.txt; echo smtp_file=$?"
```

Capture:

```powershell
ssh.exe -i id_rsa -l nama 192.168.11.6 "ls -l /dev/video0"
ssh.exe -i id_rsa -l nama 192.168.11.6 "cd /home/nama/pi; python3 controller.py --capture-only --warmup-frames 60 --save-screenshot captures/preflight.png"
```

UART/Pico:

```powershell
ssh.exe -i id_rsa -l nama 192.168.11.6 "ls -l /dev/serial0"
ssh.exe -i id_rsa -l nama 192.168.11.6 "cd /home/nama/pi; python3 hid_client.py PING"
```

WebUI:

```powershell
ssh.exe -i id_rsa -l nama 192.168.11.6 "cd /home/nama/pi; python3 app.py --host 192.168.11.6 --port 18080"
Invoke-WebRequest -UseBasicParsing -Uri http://192.168.11.6:18080/api/status -TimeoutSec 10
```

E2E list:

```powershell
.\scripts\ps1\test_e2e_suite.ps1 -List
```

### 9.4 原因分類表

| 症状 | 主な分類 | 次に確認するもの |
| --- | --- | --- |
| SSHできない | `pi_ssh` | IP、LAN、id_rsa、Pi5電源 |
| `openai-api-key.txt` がない | `pi_dependency` | Pi5の秘密ファイル配置 |
| `/dev/video0` がない | `capture_board` | USB capture 接続、device path |
| capture が黒い | `capture_board` / `target_pc_state` | HDMI、対象PC電源、入力ソース |
| `/dev/serial0` がない | `pico_uart` | UART有効化、配線、権限 |
| HID送信しても画面無変化 | `pico_uart` / `target_pc_state` | Pico firmware、USB HID認識、focus |
| OpenAI 401 | `openai_api` | API key |
| OpenAI 429 | `openai_api` | rate limit、時間を置く |
| expected_failure が成功扱い | `implementation` | 安全制御、失敗検出 |
| 通知ログがない | `implementation` / `smtp` | EventSink、SMTP設定、notification_log |
| Discord command が動かない | `discord` | token、guild/channel/user設定 |

## 10. TDD での使い方

新しい機能を実装する前に、以下を行う。

```text
1. 対応シナリオを docs/TEST_SCENARIOS.md で確認する
2. 対応テスト関数を docs/TEST_PROGRAM_SPEC.md で確認する
3. unit test を赤にする
4. integration test を赤にする
5. hardware preflight を通す
6. e2e test を赤にする
7. 最小実装で unit -> integration -> e2e の順に緑にする
8. 既存 Stage の回帰を実行する
```

実装が進んだら、`pending` を外すのではなく、テスト関数が実行可能であることを先に確認し、失敗理由が「未実装」ではなく「満たせていない期待条件」になっていることを確認する。

### 10.1 Codex / TDD skill 向けの読み替え

汎用的な TDD 手順では「失敗するテストを先に実行する」と表現するが、このプロジェクトでは失敗確認の層を必ず選ぶ。Codex は、対象変更に対して最も狭いテスト層を赤にし、必要な場合だけ Pi5 実機テストへ進む。

```text
ローカルで完結する変更:
  まず unit test を赤にする。Pi5、Pico、capture、OpenAI API は不要。

E2E ケース定義や runner 呼び出しの変更:
  まず `--call-only` を赤にする。対象 PC 操作、Pico UART、capture は実行しない。

Pi5 上の WebUI、ログ、通知、設定、依存関係の変更:
  `--run-pi-integration` を明示した integration test を赤にする。対象 PC 操作は原則不要。

Pico UART、HDMI capture、Computer Use、対象 PC の画面状態を含む変更:
  preflight を通してから `--run-hardware-e2e` を明示した Hardware E2E を赤にする。
```

Hardware E2E は外部状態を含むため、赤の意味を `implementation` と `infrastructure failure` に分ける。preflight 失敗、SSH 不通、capture 不良、Pico UART 不通、対象 PC の想定外画面、OpenAI API エラーは、実装の赤ではなく環境または外部依存の赤として扱う。実装で緑にできる赤だけを production code の修正対象にする。

Codex は、明示フラグなしの `pytest` や `scripts/ps1/test_all.ps1` を Hardware E2E 実行とみなさない。実機を使う赤/緑確認では、Pi5 への source copy、preflight、成果物確認を TDD サイクルの一部として扱う。
