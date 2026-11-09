# Builds the debug APK pointed at the cloudflared quick tunnel that is running on this PC right now.
# Usage (from anywhere):  powershell -ExecutionPolicy Bypass -File D:\inten_hackthon\android\build-for-tunnel.ps1
# Start the server and cloudflared first.
# With a fixed address (e.g. Tailscale Funnel):  ...uild-for-tunnel.ps1 -Url https://my-pc.tailXXXX.ts.net
param([string]$Url)

$hostname = $null
if ($Url) { $hostname = ($Url -replace '^https?://', '').TrimEnd('/') }
if (-not $hostname) { foreach ($port in 20241..20245) {
    try {
        $r = Invoke-RestMethod -Uri "http://127.0.0.1:$port/quicktunnel" -TimeoutSec 2
        if ($r.hostname) { $hostname = $r.hostname; break }
    } catch {}
} }
if (-not $hostname) {
    Write-Host "No cloudflared tunnel found. Start it first:  D:\tools\cloudflared.exe tunnel --url http://localhost:8787" -ForegroundColor Red
    exit 1
}
$url = "https://$hostname"
Write-Host "Tunnel: $url"

try {
    $health = Invoke-RestMethod -Uri "$url/health" -TimeoutSec 15
    Write-Host "Server reachable through the tunnel (status: $($health.status))"
} catch {
    Write-Host "Warning: the server did not answer through the tunnel. Is uvicorn running on port 8787?" -ForegroundColor Yellow
}

Push-Location $PSScriptRoot
try {
    & .\gradlew.bat :app:assembleDebug "-PserverUrl=$url" --console=plain
    if ($LASTEXITCODE -ne 0) { Write-Host "Build failed." -ForegroundColor Red; exit 1 }
} finally {
    Pop-Location
}
Write-Host ""
Write-Host "APK ready: $PSScriptRoot\app\build\outputs\apk\debug\app-debug.apk" -ForegroundColor Green
Write-Host "Uninstall the old app on the phones first (a saved old address would override the new one)."
