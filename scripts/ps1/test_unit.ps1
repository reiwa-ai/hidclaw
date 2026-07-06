param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$PytestArgs
)

$ErrorActionPreference = "Stop"
$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$python = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $python) {
    $python = "$env:USERPROFILE\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
}
Push-Location $RepoRoot
try {
    & $python -m pytest tests/unit @PytestArgs
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
