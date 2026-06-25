$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = Join-Path $Root 'venv\Scripts\python.exe'
$Port = 8000

function Get-BackendPid {
    $rows = netstat -ano | Select-String ":$Port\s"
    foreach ($row in $rows) {
        if ($row -match '\s+(\d+)$') { return [int]$Matches[1] }
    }
    return $null
}

function Start-Backend {
    $backendPid = Get-BackendPid
    if ($backendPid) { Write-Host "Backend already running on port $Port, pid=$backendPid"; return }
    Start-Process -FilePath $Python -ArgumentList 'main.py' -WorkingDirectory $Root -WindowStyle Hidden
    Start-Sleep -Seconds 4
    $backendPid = Get-BackendPid
    if ($backendPid) { Write-Host "Backend started, pid=$backendPid" } else { Write-Host 'Backend start requested, but port is not listening yet.' }
}

function Stop-Backend {
    $backendPid = Get-BackendPid
    if (-not $pid) { Write-Host 'Backend is not running.'; return }
    Stop-Process -Id $backendPid -Force
    Write-Host "Backend stopped, pid=$backendPid"
}

function Invoke-ApiPost($path) {
    Start-Backend
    $url = "http://127.0.0.1:$Port$path"
    Invoke-RestMethod -Method Post -Uri $url | ConvertTo-Json -Depth 8
}

function Health-Check {
    Start-Backend
    Invoke-RestMethod -Uri "http://127.0.0.1:$Port/api/pulse" | ConvertTo-Json -Depth 8
}

function Backup-Memory {
    $stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
    $backupDir = Join-Path $Root 'backups'
    New-Item -ItemType Directory -Force -Path $backupDir | Out-Null
    $zip = Join-Path $backupDir "memory_$stamp.zip"
    Compress-Archive -Path (Join-Path $Root 'memory') -DestinationPath $zip -Force
    Write-Host "Backup written: $zip"
}

function Show-Menu {
    Write-Host ''
    Write-Host 'Ombre Brain / Kiro maintenance'
    Write-Host '1. Start backend'
    Write-Host '2. Stop backend'
    Write-Host '3. Restart backend'
    Write-Host '4. Health check / Pulse'
    Write-Host '5. Backup memory'
    Write-Host '6. Rebuild Word Map'
    Write-Host '7. Run Dream Light'
    Write-Host '8. Run full maintenance'
    Write-Host '9. Bucket v2 migration dry-run'
    Write-Host '0. Exit'
}

while ($true) {
    Show-Menu
    $choice = Read-Host 'Choose'
    switch ($choice) {
        '1' { Start-Backend }
        '2' { Stop-Backend }
        '3' { Stop-Backend; Start-Backend }
        '4' { Health-Check }
        '5' { Backup-Memory }
        '6' { Invoke-ApiPost '/api/memory/word-map/rebuild' }
        '7' { Invoke-ApiPost '/api/dream/light/run' }
        '8' { Invoke-ApiPost '/api/maintenance/run' }
        '9' { & $Python (Join-Path $Root 'tools\migrate_buckets_v2.py') }
        '0' { break }
        default { Write-Host 'Unknown choice.' }
    }
}
