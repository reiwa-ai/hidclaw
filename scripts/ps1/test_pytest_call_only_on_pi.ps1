param(
    [string]$HostName = "192.168.11.6",
    [string]$User = "nama",
    [string]$Key = "id_rsa",
    [string]$RemoteDir = "/home/nama/pi",
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$PytestArgs
)

$ErrorActionPreference = "Stop"
$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$KeyPath = Join-Path $RepoRoot $Key
$PiPath = Join-Path $RepoRoot "pi"
$TestsPath = Join-Path $RepoRoot "tests"
$PytestIniPath = Join-Path $RepoRoot "pytest.ini"
$ConfigPath = Join-Path $RepoRoot "config"

scp.exe -i $KeyPath -r $PiPath "${User}@${HostName}:/home/${User}/"
ssh.exe -i $KeyPath -l $User $HostName "mkdir -p $RemoteDir"
scp.exe -i $KeyPath -r $TestsPath $PytestIniPath $ConfigPath "${User}@${HostName}:${RemoteDir}/"

$remoteCommand = "cd $RemoteDir; python3 -m pytest tests --call-only"
if ($PytestArgs.Count -gt 0) {
    $remoteCommand += " " + ($PytestArgs -join " ")
}

ssh.exe -i $KeyPath -l $User $HostName $remoteCommand
exit $LASTEXITCODE
