# PowerShell Test Entry Points

Run these commands from the repository root, or call the scripts by absolute path. Each script resolves the repository root from its own location.

```powershell
.\scripts\ps1\test_unit.ps1
.\scripts\ps1\test_integration.ps1 -CallOnly
.\scripts\ps1\test_pytest_call_only_on_pi.ps1 -PytestArgs @('tests/unit','-q')
.\scripts\ps1\test_e2e_suite.ps1 -Stage stage01_core_io
```

Current standard entry points:

| Script | Purpose |
| --- | --- |
| `test_unit.ps1` | Local unit pytest wrapper. |
| `test_integration.ps1` | Local integration/preflight pytest wrapper. |
| `test_e2e_pytest.ps1` | Pytest E2E wrapper for call-only or hardware-marked pytest paths. |
| `test_pytest_call_only_on_pi.ps1` | Copies source/tests/config to Pi5 and runs call-only pytest there. |
| `test_e2e_suite.ps1` | Copies `pi/` to Pi5 and runs the hardware E2E suite. |
| `test_all.ps1` | Local all-tests pytest wrapper; hardware E2E still requires explicit flags. |

Removed legacy root scripts:

- `test_prepare.ps1`: started `app.py` in the foreground and did not match current E2E flow.
- `test_test.ps1`: older short variant of `test_prepare.ps1`.
- `test_open_browser.ps1`: replaced by `test_e2e_suite.ps1 -Case stage01_scenario01_open_browser`.
