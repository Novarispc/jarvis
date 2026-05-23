"""
JARVIS Screen Awareness — see what's on the user's screen.

Two capabilities:
1. Window/app list via AppleScript (fast, text-based)
2. Screenshot via screencapture → Claude vision API (sees everything)
"""

import asyncio
import base64
import json
import logging
import sys
import tempfile
from pathlib import Path

log = logging.getLogger("jarvis.screen")

# Windows guard
_IS_WINDOWS = sys.platform == "win32"


async def get_active_windows() -> list[dict]:
    """Get list of visible windows with app name, window title, and position.

    On macOS: Uses AppleScript + System Events.
    On Windows: Uses PowerShell Get-Process to list windows with titles.
    Returns list of {"app": str, "title": str, "frontmost": bool}.
    """
    if _IS_WINDOWS:
        return await _get_active_windows_windows()

    # macOS path
    script = """
set windowList to ""
tell application "System Events"
    set frontApp to name of first application process whose frontmost is true
    set visibleApps to every application process whose visible is true
    repeat with proc in visibleApps
        set appName to name of proc
        try
            set winCount to count of windows of proc
            if winCount > 0 then
                repeat with w in (windows of proc)
                    try
                        set winTitle to name of w
                        if winTitle is not "" and winTitle is not missing value then
                            set windowList to windowList & appName & "|||" & winTitle & "|||" & (appName = frontApp) & linefeed
                        end if
                    end try
                end repeat
            end if
        end try
    end repeat
end tell
return windowList
"""
    try:
        proc = await asyncio.create_subprocess_exec(
            "osascript", "-e", script,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=5)

        if proc.returncode != 0:
            log.warning(f"get_active_windows failed: {stderr.decode()[:200]}")
            return []

        windows = []
        for line in stdout.decode().strip().split("\n"):
            parts = line.strip().split("|||")
            if len(parts) >= 3:
                windows.append({
                    "app": parts[0].strip(),
                    "title": parts[1].strip(),
                    "frontmost": parts[2].strip().lower() == "true",
                })
        return windows

    except asyncio.TimeoutError:
        log.warning("get_active_windows timed out")
        return []
    except Exception as e:
        log.warning(f"get_active_windows error: {e}")
        return []


async def _get_active_windows_windows() -> list[dict]:
    """Windows fallback: use PowerShell to list processes with visible windows."""
    ps_cmd = (
        "Get-Process | Where-Object {$_.MainWindowTitle -ne ''} | "
        "Select-Object ProcessName, MainWindowTitle | "
        "ForEach-Object { $_.ProcessName + '|||' + $_.MainWindowTitle }"
    )
    try:
        proc = await asyncio.create_subprocess_exec(
            "powershell", "-NoProfile", "-Command", ps_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=8)
        windows = []
        first = True
        for line in stdout.decode().strip().split("\n"):
            parts = line.strip().split("|||")
            if len(parts) >= 2 and parts[0].strip():
                windows.append({
                    "app": parts[0].strip(),
                    "title": parts[1].strip(),
                    "frontmost": first,  # first result is usually the foreground app
                })
                first = False
        return windows
    except asyncio.TimeoutError:
        log.warning("get_active_windows (Windows) timed out")
        return []
    except Exception as e:
        log.warning(f"get_active_windows (Windows) error: {e}")
        return []


async def get_running_apps() -> list[str]:
    """Get list of running application names (visible only)."""
    if _IS_WINDOWS:
        # On Windows, derive from get_active_windows
        windows = await _get_active_windows_windows()
        return list(dict.fromkeys(w["app"] for w in windows))

    script = """
tell application "System Events"
    set appNames to name of every application process whose visible is true
    set output to ""
    repeat with a in appNames
        set output to output & a & linefeed
    end repeat
    return output
end tell
"""
    try:
        proc = await asyncio.create_subprocess_exec(
            "osascript", "-e", script,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=5)
        if proc.returncode == 0:
            return [a.strip() for a in stdout.decode().strip().split("\n") if a.strip()]
        return []
    except Exception as e:
        log.warning(f"get_running_apps error: {e}")
        return []


async def take_screenshot(display_only: bool = True) -> str | None:
    """Take a screenshot and return base64-encoded PNG.

    On macOS: uses screencapture.
    On Windows: uses PowerShell with System.Windows.Forms.Screen.
    Returns:
        Base64-encoded PNG string, or None on failure.
    """
    if _IS_WINDOWS:
        return await _take_screenshot_windows()

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        tmp_path = f.name

    try:
        cmd = ["screencapture", "-x"]  # -x = no sound
        if display_only:
            cmd.append("-m")  # main display only
        cmd.append(tmp_path)

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await asyncio.wait_for(proc.communicate(), timeout=10)

        if proc.returncode != 0 or not Path(tmp_path).exists():
            log.warning("Screenshot capture failed")
            return None

        data = Path(tmp_path).read_bytes()
        log.info(f"Screenshot captured: {len(data)} bytes")
        return base64.b64encode(data).decode()

    except asyncio.TimeoutError:
        log.warning("Screenshot timed out")
        return None
    except Exception as e:
        log.warning(f"Screenshot error: {e}")
        return None
    finally:
        try:
            Path(tmp_path).unlink(missing_ok=True)
        except Exception:
            pass


async def _take_screenshot_windows() -> str | None:
    """Windows screenshot via PowerShell + System.Drawing."""
    import uuid
    tmp_path = Path(tempfile.gettempdir()) / f"jarvis_shot_{uuid.uuid4().hex}.png"
    ps_cmd = (
        "Add-Type -AssemblyName System.Windows.Forms; "
        "Add-Type -AssemblyName System.Drawing; "
        "$screen = [System.Windows.Forms.Screen]::PrimaryScreen; "
        "$bmp = New-Object System.Drawing.Bitmap($screen.Bounds.Width, $screen.Bounds.Height); "
        "$g = [System.Drawing.Graphics]::FromImage($bmp); "
        f"$g.CopyFromScreen($screen.Bounds.Location, [System.Drawing.Point]::Empty, $screen.Bounds.Size); "
        f"$bmp.Save('{tmp_path}'); "
        "$g.Dispose(); $bmp.Dispose()"
    )
    try:
        proc = await asyncio.create_subprocess_exec(
            "powershell", "-NoProfile", "-Command", ps_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await asyncio.wait_for(proc.communicate(), timeout=15)
        if tmp_path.exists():
            data = tmp_path.read_bytes()
            log.info(f"Windows screenshot captured: {len(data)} bytes")
            return base64.b64encode(data).decode()
        log.warning("Windows screenshot: file not created")
        return None
    except asyncio.TimeoutError:
        log.warning("Windows screenshot timed out")
        return None
    except Exception as e:
        log.warning(f"Windows screenshot error: {e}")
        return None
    finally:
        try:
            tmp_path.unlink(missing_ok=True)
        except Exception:
            pass


async def describe_screen() -> str:
    """Describe what's on the user's screen.

    Tries screenshot + vision first. Falls back to window list + LLM summary.
    """
    # Get window list for LLM summary
    windows = await get_active_windows()
    apps = await get_running_apps()

    if not windows and not apps:
        return "I wasn't able to see your screen, sir. Screen recording permission may be needed."

    # Build a text description for LLM to summarize
    context_parts = []
    if windows:
        for w in windows:
            marker = " (ACTIVE)" if w["frontmost"] else ""
            context_parts.append(f"{w['app']}: {w['title']}{marker}")

    if apps:
        window_apps = set(w["app"] for w in windows) if windows else set()
        bg_apps = [a for a in apps if a not in window_apps]
        if bg_apps:
            context_parts.append(f"Background apps: {', '.join(bg_apps)}")

    if context_parts:
        # Plain text fallback — no LLM dependency for screen
        pass

    # Raw fallback
    if windows:
        active = next((w for w in windows if w["frontmost"]), None)
        result = f"You have {len(windows)} windows open across {len(set(w['app'] for w in windows))} apps."
        if active:
            result += f" Currently focused on {active['app']}: {active['title']}."
        return result

    return f"Running apps: {', '.join(apps)}. Couldn't read window titles, sir."


def format_windows_for_context(windows: list[dict]) -> str:
    """Format window list as context string for the LLM."""
    if not windows:
        return ""
    lines = ["Currently open on your desktop:"]
    for w in windows:
        marker = " (active)" if w["frontmost"] else ""
        lines.append(f"  - {w['app']}: {w['title']}{marker}")
    return "\n".join(lines)
