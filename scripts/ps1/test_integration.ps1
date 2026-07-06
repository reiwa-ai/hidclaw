param(
    [switch]$CallOnly,
    [switch]$RunPiIntegration,
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$PytestArgs
)

$ErrorActionPreference = "Stop"
$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$python = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $python) {
    $python = "$env:USERPROFILE\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
}
$argsList = @("tests/integration", "tests/preflight")

if ($CallOnly) {
    $argsList += "--call-only"
}

if ($RunPiIntegration) {
    $argsList += "--run-pi-integration"
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
