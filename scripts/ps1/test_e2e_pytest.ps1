param(
    [switch]$CallOnly,
    [switch]$RunHardwareE2E,
    [string]$Stage = "",
    [string]$Case = "",
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$PytestArgs
)

$ErrorActionPreference = "Stop"
$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$python = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $python) {
    $python = "$env:USERPROFILE\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
}
$argsList = @("tests/e2e")

if ($CallOnly) {
    $argsList += "--call-only"
}

if ($RunHardwareE2E) {
    $argsList += "--run-hardware-e2e"
}

if ($Stage -ne "") {
    $argsList += "--e2e-stage"
    $argsList += $Stage
}

if ($Case -ne "") {
    $argsList += "--e2e-case"
    $argsList += $Case
}

$argsList += $PytestArgs
Push-Location $RepoRoot
try {
    & $python -m pytest @argsList
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
