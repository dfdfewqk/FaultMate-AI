# Windows batch-launch integration smoke.
# Exercises the real start_windows.bat with a fresh .venv; no DeepSeek calls,
# no persistent changes or source data writes. Intended for GitHub Windows runner.
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Set-Location $root
$env:FAULTMATE_NO_BROWSER = '1'
Remove-Item Env:DEEPSEEK_API_KEY -ErrorAction SilentlyContinue
$portText = (& '.\.venv\Scripts\python.exe' -c "import socket;s=socket.socket();s.bind(('127.0.0.1',0));print(s.getsockname()[1]);s.close()").Trim()
if ($LASTEXITCODE -ne 0) { throw 'Could not select a free loopback port' }
$env:FAULTMATE_PORT = $portText
$base = "http://127.0.0.1:$portText"
$stdout = Join-Path $env:RUNNER_TEMP 'faultmate-windows-stdout.log'
$stderr = Join-Path $env:RUNNER_TEMP 'faultmate-windows-stderr.log'

$launcher = $null
try {
    $launcher = Start-Process -FilePath 'cmd.exe' -ArgumentList '/d', '/c', 'start_windows.bat' -WorkingDirectory $root -PassThru -WindowStyle Hidden -RedirectStandardOutput $stdout -RedirectStandardError $stderr
    $ready = $false
    for ($i = 0; $i -lt 80; $i++) {
        Start-Sleep -Milliseconds 500
        if ($launcher.HasExited) {
            throw "Batch launcher exited before readiness: $($launcher.ExitCode)"
        }
        try {
            $status = Invoke-RestMethod "$base/api/status" -TimeoutSec 2
            if ($status.app -eq 'FaultMate AI') { $ready = $true; break }
        } catch {
            # Server not yet listening.
        }
    }
    if (-not $ready) { throw 'Windows server did not become ready in 40 seconds' }
    $null = Invoke-WebRequest -Uri "$base/" -TimeoutSec 5 -UseBasicParsing
    $null = Invoke-WebRequest -Uri "$base/assets/app.js" -TimeoutSec 5 -UseBasicParsing
    $null = Invoke-WebRequest -Uri "$base/assets/style.css" -TimeoutSec 5 -UseBasicParsing
    $options = Invoke-RestMethod "$base/api/diagnostics/options" -TimeoutSec 5
    if ($null -eq $options) { throw 'Diagnostic options endpoint returned no data' }
    $capabilities = Invoke-RestMethod "$base/api/integration/capabilities" -TimeoutSec 5
    if ($capabilities.ml.inference_enabled -ne $false) { throw 'Unreviewed ML model unexpectedly enabled' }
    if ($capabilities.agent.connected -ne $false) { throw 'DeepSeek connected despite missing API key' }
    $payload = '{"case_id":"CONV-001","emergency_hazard":"yes"}'
    $result = Invoke-RestMethod -Uri "$base/api/diagnostics/evaluate" -Method Post -ContentType 'application/json' -Body $payload -TimeoutSec 5
    if ($result.state -ne 'safety_hold') { throw "Unsafe hazard response: $($result.state)" }
    if ($result.confirmed_fault -eq $true -or $result.safe_to_work -eq $true) {
        throw 'Safety authorization must always remain false'
    }
    Write-Output 'WINDOWS_BATCH_SMOKE_PASS: startup, index, JS, CSS, diagnostics, capabilities, safety hold'
}
finally {
    if ($launcher -ne $null) {
        & taskkill.exe /PID $launcher.Id /T /F 2>$null | Out-Null
    }
    if (Test-Path $stdout) { Get-Content $stdout -Tail 35 }
    if (Test-Path $stderr) { Get-Content $stderr -Tail 35 }
}
