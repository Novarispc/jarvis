# ============================================================
#  STOP_JARVIS.ps1
#  Run this to gracefully shut down JARVIS.
#  Right-click → "Run with PowerShell"
# ============================================================

$JARVIS_DIR = "$HOME\jarvis"
$PID_FILE   = "$JARVIS_DIR\.jarvis_pids.json"

Write-Host ""
Write-Host "  Shutting down JARVIS..." -ForegroundColor Yellow

# ── Stop by saved PIDs ─────────────────────────────────────
if (Test-Path $PID_FILE) {
    try {
        $pids = Get-Content $PID_FILE | ConvertFrom-Json
        foreach ($pid in @($pids.BackendPID, $pids.FrontendPID)) {
            if ($pid) {
                Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
                Write-Host "  Stopped PID $pid" -ForegroundColor Gray
            }
        }
        Remove-Item $PID_FILE -Force
    } catch {
        Write-Host "  Could not read PID file — stopping by process name instead." -ForegroundColor Yellow
    }
}

# ── Also kill any remaining Python/node JARVIS processes ───
$killed = 0
Get-Process -Name python, node -ErrorAction SilentlyContinue | ForEach-Object {
    $_.Kill()
    $killed++
}
if ($killed -gt 0) {
    Write-Host "  Stopped $killed additional process(es)" -ForegroundColor Gray
}

Write-Host ""
Write-Host "  JARVIS is offline, sir." -ForegroundColor Cyan
Write-Host ""
