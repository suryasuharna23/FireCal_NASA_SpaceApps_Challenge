param([switch]$NoBrowser)

$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$owned = @()
$logDir = Join-Path $PSScriptRoot 'data\live'
New-Item -ItemType Directory -Path $logDir -Force | Out-Null

function Test-Url([string]$Url) {
    try { return (Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 2).StatusCode -eq 200 }
    catch { return $false }
}

try {
    $python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
    if (!(Test-Path -LiteralPath $python)) {
        if (!(Get-Command uv -ErrorAction SilentlyContinue)) {
            throw 'Install uv first, then run .\run.ps1 again.'
        }
        & uv sync --all-packages --locked --python 3.12
        if ($LASTEXITCODE -ne 0) { throw 'Python dependency installation failed.' }
    }
    if (!(Get-Command node.exe -ErrorAction SilentlyContinue)) { throw 'Install Node.js 22 or newer first.' }
    $vite = Join-Path $PSScriptRoot 'web\node_modules\vite\bin\vite.js'
    if (!(Test-Path -LiteralPath $vite)) {
        & npm.cmd exec --yes --package=pnpm@10.33.2 -- pnpm --dir web install --frozen-lockfile
        if ($LASTEXITCODE -ne 0) { throw 'Frontend dependency installation failed.' }
    }

    if (!(Test-Url 'http://127.0.0.1:8000/health')) {
        if (Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue) {
            throw 'Port 8000 is occupied by another program.'
        }
        $owned += Start-Process -FilePath $python -ArgumentList @('-m','firecal.cli','serve') `
            -WorkingDirectory $PSScriptRoot -WindowStyle Hidden -PassThru `
            -RedirectStandardOutput (Join-Path $logDir 'api.stdout.log') `
            -RedirectStandardError (Join-Path $logDir 'api.stderr.log')
    }
    if (!(Test-Url 'http://127.0.0.1:5173')) {
        if (Get-NetTCPConnection -LocalPort 5173 -State Listen -ErrorAction SilentlyContinue) {
            throw 'Port 5173 is occupied by another program.'
        }
        $owned += Start-Process -FilePath (Get-Command node.exe).Source `
            -ArgumentList @('node_modules/vite/bin/vite.js','--host','127.0.0.1') `
            -WorkingDirectory (Join-Path $PSScriptRoot 'web') -WindowStyle Hidden -PassThru `
            -RedirectStandardOutput (Join-Path $logDir 'web.stdout.log') `
            -RedirectStandardError (Join-Path $logDir 'web.stderr.log')
    }
    $deadline = (Get-Date).AddMinutes(3)
    while (!(Test-Url 'http://127.0.0.1:8000/health') -or !(Test-Url 'http://127.0.0.1:5173')) {
        if ((Get-Date) -gt $deadline -or @($owned | Where-Object { $_.HasExited }).Count) {
            throw 'Startup failed. Check data/live/api.stderr.log and web.stderr.log.'
        }
        Start-Sleep -Seconds 1
    }
    $meta = Invoke-RestMethod 'http://127.0.0.1:8000/meta'
    if ($meta.status -ne 'ok' -or $meta.coverage.country -ne 'Indonesia') {
        throw 'The API is running without the expected real Indonesia data.'
    }
    Write-Host 'FireCal: http://localhost:5173'
    Write-Host "Real observations through $($meta.last_acq_date). NASA catch-up runs in the backend."
    if (!$NoBrowser) { Start-Process 'http://localhost:5173' }
    if (!$owned.Count) { Write-Host 'Both services were already running.'; return }
    Write-Host 'Keep this terminal open. Press Ctrl+C to stop the services started here.'
    while ($true) {
        if (@($owned | Where-Object { $_.HasExited }).Count) { throw 'A service stopped; check data/live logs.' }
        Start-Sleep -Seconds 1
    }
}
finally {
    foreach ($process in $owned) {
        if (!$process.HasExited) { & taskkill.exe /PID $process.Id /T /F 2>$null | Out-Null }
    }
}
