# ============================================================
#  START_JARVIS.ps1
#  Run this script every time you want to use JARVIS.
#  Right-click → "Run with PowerShell"  (or double-click)
# ============================================================

$JARVIS_DIR = "$HOME\jarvis"
$VENV_PYTHON = "$JARVIS_DIR\venv\Scripts\python.exe"

Write-Host ""
Write-Host "  J.A.R.V.I.S. Startup" -ForegroundColor Cyan
Write-Host "  =====================" -ForegroundColor Cyan
Write-Host ""

# ── Sanity checks ──────────────────────────────────────────
if (-not (Test-Path $VENV_PYTHON)) {
    Write-Host "  ERROR: Python venv not found." -ForegroundColor Red
    Write-Host "  Run this first: python -m venv venv" -ForegroundColor Yellow
    Read-Host "  Press Enter to exit"
    exit 1
}

if (-not (Test-Path "$JARVIS_DIR\.env")) {
    Write-Host "  ERROR: .env file missing." -ForegroundColor Red
    Write-Host "  Copy .env.example to .env and add your API keys." -ForegroundColor Yellow
    Read-Host "  Press Enter to exit"
    exit 1
}

# ── Check Ollama mode ──────────────────────────────────────
$envContent = Get-Content "$JARVIS_DIR\.env" -ErrorAction SilentlyContinue
$useOllama = $envContent | Where-Object { $_ -match "^USE_OLLAMA\s*=\s*(true|1)" }
if ($useOllama) {
    Write-Host "  Mode: OFFLINE (Ollama)" -ForegroundColor Yellow
    try {
        $req = [System.Net.WebRequest]::Create("http://localhost:11434")
        $req.Timeout = 3000
        $resp = $req.GetResponse()
        $resp.Close()
        Write-Host "  Ollama: ONLINE" -ForegroundColor Green
    } catch {
        Write-Host "  WARNING: Ollama may not be running at localhost:11434" -ForegroundColor Yellow
        Write-Host "  If JARVIS doesn't respond, run: ollama serve" -ForegroundColor Yellow
    }
} else {
    Write-Host "  Mode: ONLINE (Claude / Anthropic)" -ForegroundColor Green
}

Write-Host ""

# ── Start Backend (silent — logs go to server_out.txt / server_err.txt) ──
Write-Host "  [1/2] Starting JARVIS backend (port 8340)..." -ForegroundColor White
$backend = Start-Process -FilePath $VENV_PYTHON `
    -ArgumentList "$JARVIS_DIR\server.py" `
    -WorkingDirectory $JARVIS_DIR `
    -RedirectStandardOutput "$JARVIS_DIR\server_out.txt" `
    -RedirectStandardError  "$JARVIS_DIR\server_err.txt" `
    -WindowStyle Hidden `
    -PassThru
Start-Sleep -Seconds 5

if ($backend.HasExited) {
    Write-Host "  ERROR: Backend crashed on startup!" -ForegroundColor Red
    Write-Host "  Check server_err.txt for details." -ForegroundColor Yellow
    Get-Content "$JARVIS_DIR\server_err.txt" -Tail 10 | ForEach-Object { Write-Host "  $_" -ForegroundColor Red }
    Read-Host "  Press Enter to exit"
    exit 1
}
Write-Host "  Backend running (PID $($backend.Id))" -ForegroundColor Green

# ── Start Frontend (silent — logs go to frontend_out.txt) ──────────────
Write-Host "  [2/2] Starting JARVIS frontend (port 5173)..." -ForegroundColor White
$npmCmd = "cd /d `"$JARVIS_DIR\frontend`" && npm run dev > `"$JARVIS_DIR\frontend_out.txt`" 2>&1"
$frontend = Start-Process -FilePath "cmd.exe" `
    -ArgumentList "/c", $npmCmd `
    -WindowStyle Hidden `
    -PassThru
Start-Sleep -Seconds 7

# Verify frontend started
$fe5173 = netstat -ano | findstr ":5173"
if (-not $fe5173) {
    Write-Host "  ERROR: Frontend failed to start!" -ForegroundColor Red
    Write-Host "  Check frontend_out.txt for details." -ForegroundColor Yellow
    Read-Host "  Press Enter to exit"
    exit 1
}
Write-Host "  Frontend running (PID $($frontend.Id))" -ForegroundColor Green

# ── Save PIDs for STOP script ──────────────────────────────
@{
    BackendPID  = $backend.Id
    FrontendPID = $frontend.Id
    StartedAt   = (Get-Date).ToString("o")
} | ConvertTo-Json | Set-Content "$JARVIS_DIR\.jarvis_pids.json"

# ── Open Chrome automatically ──────────────────────────────
Start-Sleep -Seconds 1
Start-Process "chrome.exe" "http://localhost:5173" -ErrorAction SilentlyContinue

# ── Done ───────────────────────────────────────────────────
Write-Host ""
Write-Host "  ============================================" -ForegroundColor Cyan
Write-Host "  JARVIS is ready, sir." -ForegroundColor Green
Write-Host ""
Write-Host "  Chrome opened at http://localhost:5173" -ForegroundColor Yellow
Write-Host "  Logs: server_err.txt / frontend_out.txt" -ForegroundColor Gray
Write-Host ""
Write-Host "  Say 'Jarvis' to wake, or click the orb." -ForegroundColor White
Write-Host ""
Write-Host "  To stop JARVIS, run STOP_JARVIS.ps1" -ForegroundColor Gray
Write-Host "  ============================================" -ForegroundColor Cyan
Write-Host ""
Read-Host "  Press Enter to close this window"
