<#
.SYNOPSIS
  Deploys the Sarvagyan server from this PC to your free cloud server (Azure for Students or Oracle Cloud),
  then builds the APK for it.

.DESCRIPTION
  First time (after creating the server: docs/DEPLOY_AZURE.md steps 1-3, or docs/DEPLOY_ORACLE.md steps 1-4):
      powershell -ExecutionPolicy Bypass -File D:\inten_hackthon\deploy\deploy-from-pc.ps1
  Later, to put new code on the server (users stay signed in):
      powershell -ExecutionPolicy Bypass -File D:\inten_hackthon\deploy\deploy-from-pc.ps1 -Update

  The code is uploaded straight from this folder (nothing has to be pushed to GitHub). The Gnani key is read from
  this repository's .env; a DuckDNS token (only if you use DuckDNS) is asked for and never saved on this PC. The server
  IP, SSH user, key path and web address are remembered in deploy\.deploy.local.json (no secrets in it).
#>
param(
    [switch]$Update,
    [switch]$NoApk,
    [string]$Ip,
    [string]$Key,
    [string]$User,
    [string]$Domain
)
$ErrorActionPreference = 'Stop'
$repo = Split-Path $PSScriptRoot -Parent
$saved = Join-Path $PSScriptRoot '.deploy.local.json'

function Step($text) { Write-Host "`n==> $text" -ForegroundColor Green }
function Fail($text) { Write-Host $text -ForegroundColor Red; exit 1 }
function BashQuote($v) { "'" + ($v -replace "'", "'\''") + "'" }

# --- remembered settings -------------------------------------------------------------------------------------
$cfg = @{ Ip = ''; Key = "$env:USERPROFILE\.ssh\sarvagyan.key"; User = ''; Domain = '' }
if (Test-Path $saved) {
    $j = Get-Content $saved -Raw | ConvertFrom-Json
    foreach ($k in 'Ip', 'Key', 'User', 'Domain') { if ($j.$k) { $cfg[$k] = $j.$k } }
    if (-not $cfg.Domain -and $j.DuckName) { $cfg.Domain = "$($j.DuckName).duckdns.org"; $cfg.User = 'ubuntu' }
}
if ($Ip) { $cfg.Ip = $Ip }
if ($Key) { $cfg.Key = $Key }
if ($User) { $cfg.User = $User }
if ($Domain) { $cfg.Domain = $Domain }
if (-not $cfg.Ip) { $cfg.Ip = (Read-Host 'Server public IP address').Trim() }
if (-not $cfg.User) {
    $entered = (Read-Host 'SSH user name [azureuser]  (Oracle: ubuntu)').Trim()
    $cfg.User = if ($entered) { $entered } else { 'azureuser' }
}
if (-not (Test-Path $cfg.Key)) {
    $entered = Read-Host "Path of the SSH private key you saved from Oracle [$($cfg.Key)]"
    if ($entered) { $cfg.Key = $entered }
}
if (-not (Test-Path $cfg.Key)) { Fail "SSH key not found: $($cfg.Key)" }
if (-not $cfg.Domain) {
    $cfg.Domain = (Read-Host 'Server web address (Azure: name.region.cloudapp.azure.com, or a DuckDNS name)').Trim()
}
$cfg.Domain = $cfg.Domain -replace '^https?://', '' -replace '/.*$', ''
if ($cfg.Domain -notmatch '\.') { $cfg.Domain = "$($cfg.Domain).duckdns.org" }
$cfg | ConvertTo-Json | Set-Content $saved -Encoding UTF8
$domain = $cfg.Domain
$useDuck = $domain -like '*.duckdns.org'
$target = "$($cfg.User)@$($cfg.Ip)"
$ssh = @('-i', $cfg.Key, '-o', 'StrictHostKeyChecking=accept-new', '-o', 'ConnectTimeout=20')

# --- reach the server ----------------------------------------------------------------------------------------
Step "Connecting to $target"
& ssh @ssh $target 'echo connected' | Out-Null
if ($LASTEXITCODE -ne 0) {
    Fail ("Can't connect. Check the IP, that the server is Running, and the key file. " +
          "If Windows says the key's permissions are too open, run:`n  icacls `"$($cfg.Key)`" /inheritance:r /grant:r `"$($env:USERNAME):(R)`"")
}

# --- upload the code -----------------------------------------------------------------------------------------
Step 'Packing and uploading the server code'
$tgz = Join-Path $env:TEMP 'sarvagyan-deploy.tgz'
Remove-Item $tgz -ErrorAction SilentlyContinue
& tar -czf $tgz -C $repo --exclude '.venv' --exclude 'data' --exclude '__pycache__' --exclude '.pytest_cache' --exclude '.env' server deploy
if ($LASTEXITCODE -ne 0) { Fail 'Packing the code failed.' }
& scp @ssh $tgz "${target}:/tmp/sarvagyan.tgz"
if ($LASTEXITCODE -ne 0) { Fail 'Upload failed.' }
Remove-Item $tgz
& ssh @ssh $target 'rm -rf ~/sarvagyan && mkdir -p ~/sarvagyan && tar -xzf /tmp/sarvagyan.tgz -C ~/sarvagyan && rm /tmp/sarvagyan.tgz'
if ($LASTEXITCODE -ne 0) { Fail 'Unpacking on the server failed.' }

if ($Update) {
    Step 'Updating and restarting the server'
    & ssh @ssh $target 'cd ~/sarvagyan && bash deploy/update.sh'
    if ($LASTEXITCODE -ne 0) { Fail 'Update failed. See the messages above.' }
} else {
    # --- first-time setup: settings go to the server in a short-lived file, deleted right after use ------------
    $envFile = Join-Path $repo '.env'
    $gnani = ''
    $mymemory = ''
    if (Test-Path $envFile) {
        foreach ($line in Get-Content $envFile) {
            if ($line -match '^GNANI_API_KEY=(.*)$') { $gnani = $Matches[1].Trim() }
            if ($line -match '^MYMEMORY_EMAIL=(.*)$') { $mymemory = $Matches[1].Trim() }
        }
    }
    if (-not $gnani) {
        $s = Read-Host 'Gnani API key' -AsSecureString
        $gnani = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($s))
    } else { Write-Host 'Using the Gnani key from this repository''s .env' }
    $token = ''
    if ($useDuck) {
        $t = Read-Host 'DuckDNS token (from duckdns.org)' -AsSecureString
        $token = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($t))
    }
    if (-not $mymemory) { $mymemory = (Read-Host 'Email for MyMemory''s higher free translation quota (Enter to skip)').Trim() }
    $guest = Read-Host "Allow 'Continue as guest' sign-in? [Y/n]"
    $demo = if ($guest -match '^[Nn]') { 'false' } else { 'true' }

    $lines = @(
        'set -e'
        "export DOMAIN=$(BashQuote $domain)"
        "export DUCK_TOKEN=$(BashQuote $token)"
        "export GNANI_KEY=$(BashQuote $gnani)"
        "export MYMEMORY_EMAIL=$(BashQuote $mymemory)"
        "export DEMO_MODE=$demo"
        'rm -f "$0"'
        'cd ~/sarvagyan && bash deploy/setup.sh'
    )
    $local = Join-Path $env:TEMP 'sarvagyan-setup.sh'
    [IO.File]::WriteAllText($local, (($lines -join "`n") + "`n"))  # Linux line endings
    # create the file as private (600) first; scp then writes into it and keeps those permissions
    & ssh @ssh $target 'umask 077; : > ~/.sarvagyan-setup.sh'
    & scp @ssh $local "${target}:.sarvagyan-setup.sh"
    $sent = $LASTEXITCODE
    Remove-Item $local
    if ($sent -ne 0) { Fail 'Sending the settings to the server failed.' }
    $token = $null; $gnani = $null

    Step 'Setting up the server (about 5 minutes)'
    & ssh @ssh $target 'bash ~/.sarvagyan-setup.sh'
    if ($LASTEXITCODE -ne 0) {
        & ssh @ssh $target 'rm -f ~/.sarvagyan-setup.sh'
        Fail 'Setup stopped with an error. See the messages above.'
    }
}

# --- wait until it answers over HTTPS ------------------------------------------------------------------------
Step "Waiting for https://$domain to answer"
$ok = $false
for ($i = 0; $i -lt 24 -and -not $ok; $i++) {
    try {
        $r = Invoke-WebRequest "https://$domain/health" -UseBasicParsing -TimeoutSec 10
        if ($r.StatusCode -eq 200) { $ok = $true; Write-Host $r.Content }
    } catch { Start-Sleep -Seconds 10 }
}
if (-not $ok) {
    Fail ("No answer yet. Check ports TCP 80 and 443 are open in the cloud firewall (Azure: Networking tab; " +
          "Oracle: security list), that $domain points to $($cfg.Ip), " +
          "then open https://$domain/health in a browser in a few minutes.")
}

if ($NoApk) { Write-Host "`nServer is live at https://$domain" -ForegroundColor Green; exit 0 }

# --- build the app for this server -----------------------------------------------------------------------------
Step "Building the app for https://$domain"
& "$repo\android\gradlew.bat" -p "$repo\android" :app:assembleDebug "-PserverUrl=https://$domain" --console=plain -q
if ($LASTEXITCODE -ne 0) { Fail 'The app build failed. See the messages above.' }
Write-Host "`nDone. Server: https://$domain" -ForegroundColor Green
Write-Host "APK: $repo\android\app\build\outputs\apk\debug\app-debug.apk"
Write-Host 'Uninstall the old app on the phones first, then install this one. You never need to rebuild for a new address again.'
