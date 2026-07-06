param(
    [string]$Stage = "",
    [string]$Case = "",
    [switch]$List,
    [switch]$IncludePending
)

$ErrorActionPreference = "Stop"
$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$KeyPath = Join-Path $RepoRoot "id_rsa"
$PiPath = Join-Path $RepoRoot "pi"

scp.exe -i $KeyPath -r $PiPath nama@192.168.11.6:/home/nama/
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

if ($List) {
    $remoteCommand = "cd /home/nama/pi; python3 run_e2e_suite.py"
} else {
    $remoteCommand = "cd /home/nama/pi; pip3 install --break-system-packages -r requirements.txt; python3 run_e2e_suite.py --api-key-file /home/nama/openai-api-key.txt --api-timeout 60"
}


if ($Stage -ne "") {
    $remoteCommand += " --stage $Stage"
}

if ($Case -ne "") {
    $remoteCommand += " --case $Case"
}

if ($List) {
    $remoteCommand += " --list"
}

if ($IncludePending) {
    $remoteCommand += " --include-pending"
}

ssh.exe -i $KeyPath -l nama 192.168.11.6 $remoteCommand
exit $LASTEXITCODE
