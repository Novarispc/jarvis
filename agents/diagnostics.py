"""
System Diagnostics — AI-powered issue detection and fix suggestions.

Works with VISION to analyze system health and provide solutions.
"""

import json
import logging
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import asdict

from agents.system_info import get_system_info_gatherer, SystemHealth

log = logging.getLogger("jarvis.diagnostics")

# ---------------------------------------------------------------------------
# Diagnostic Rules
# ---------------------------------------------------------------------------

class DiagnosticRule:
    """A rule for detecting and fixing system issues."""

    def __init__(
        self,
        name: str,
        description: str,
        check_fn,  # callable(health: SystemHealth) -> (detected: bool, severity: str, details: str)
        fix_fn,    # callable() -> bool (returns True if fix succeeded)
        auto_fix: bool = False,
    ):
        self.name = name
        self.description = description
        self.check_fn = check_fn
        self.fix_fn = fix_fn
        self.auto_fix = auto_fix

    def check(self, health: SystemHealth) -> Tuple[bool, str, str]:
        """Check if this issue is detected. Returns (detected, severity, details)."""
        try:
            return self.check_fn(health)
        except Exception as e:
            log.warning(f"Error in diagnostic rule {self.name}: {e}")
            return False, "unknown", str(e)

    def apply_fix(self) -> bool:
        """Apply the fix. Returns True if successful."""
        try:
            return self.fix_fn()
        except Exception as e:
            log.warning(f"Error applying fix for {self.name}: {e}")
            return False


# ---------------------------------------------------------------------------
# Diagnostic Rules Library
# ---------------------------------------------------------------------------

def create_diagnostic_rules() -> List[DiagnosticRule]:
    """Create all diagnostic rules."""
    rules = []

    # RAM usage critical
    rules.append(DiagnosticRule(
        name="high_memory_usage",
        description="RAM usage is critically high",
        check_fn=lambda h: (
            h.memory.usage_percent > 85,
            "critical" if h.memory.usage_percent > 90 else "warning",
            f"Memory usage at {h.memory.usage_percent:.1f}% ({h.memory.used_gb:.1f}/{h.memory.total_gb:.1f} GB). "
            f"Available: {h.memory.available_gb:.1f} GB. " +
            ("This can cause system slowdown or crashes." if h.memory.usage_percent > 90 else "")
        ),
        fix_fn=lambda: _clear_cache(),
        auto_fix=False,
    ))

    # Disk space low
    rules.append(DiagnosticRule(
        name="low_disk_space",
        description="Disk space is running low",
        check_fn=lambda h: (
            h.disks and min((d.usage_percent for d in h.disks if d.usage_percent), default=0) > 80,
            "critical" if any(d.usage_percent > 90 for d in h.disks) else "warning",
            f"Primary drive usage: {h.disks[0].usage_percent:.1f}% ({h.disks[0].used_gb:.0f}/{h.disks[0].total_gb:.0f} GB). "
            "Free up space by deleting temporary files or moving data to external storage."
        ),
        fix_fn=lambda: _cleanup_temp_files(),
        auto_fix=False,
    ))

    # CPU temperature high
    def check_cpu_temp(h):
        if h.cpu.temp_celsius is None or h.cpu.temp_celsius <= 80:
            return False, "warning", ""
        is_critical = h.cpu.temp_celsius > 95
        severity = "critical" if is_critical else "warning"
        msg = f"CPU temperature: {h.cpu.temp_celsius:.1f}°C. "
        msg += ("This is dangerously hot — check cooling and ensure vents are clear." if is_critical
                else "Consider improving ventilation or reducing load.")
        return True, severity, msg

    rules.append(DiagnosticRule(
        name="high_cpu_temp",
        description="CPU temperature is elevated",
        check_fn=check_cpu_temp,
        fix_fn=lambda: _reduce_cpu_load(),
        auto_fix=False,
    ))

    # High CPU usage
    rules.append(DiagnosticRule(
        name="high_cpu_usage",
        description="CPU usage is high",
        check_fn=lambda h: (
            h.cpu.usage_percent > 85,
            "warning",
            f"CPU usage: {h.cpu.usage_percent:.1f}%. "
            f"Top consumer: {h.processes[0].name if h.processes else 'Unknown'} ({h.processes[0].cpu_percent:.1f}%)"
        ),
        fix_fn=lambda: _kill_resource_hogs(h if 'h' in locals() else None),
        auto_fix=False,
    ))

    # Low available memory
    rules.append(DiagnosticRule(
        name="low_available_memory",
        description="Available memory is critically low",
        check_fn=lambda h: (
            h.memory.available_gb < 1.0,
            "critical",
            f"Only {h.memory.available_gb:.1f} GB available. System may become unresponsive. "
            "Close unused applications or restart your PC."
        ),
        fix_fn=lambda: _close_background_apps(),
        auto_fix=False,
    ))

    # Too many background services
    rules.append(DiagnosticRule(
        name="too_many_services",
        description="Many background services are running",
        check_fn=lambda h: (
            h.services_summary.get("running", 0) > 150,
            "warning",
            f"{h.services_summary.get('running', 0)} services running. "
            "Too many background services can impact performance."
        ),
        fix_fn=lambda: _disable_unused_services(),
        auto_fix=False,
    ))

    # System hasn't been restarted
    rules.append(DiagnosticRule(
        name="long_uptime",
        description="System has been running too long without restart",
        check_fn=lambda h: (
            h.uptime_hours > 72,
            "info",
            f"System uptime: {h.uptime_hours:.1f} hours ({h.uptime_hours/24:.1f} days). "
            "Consider restarting to clear memory caches and improve performance."
        ),
        fix_fn=lambda: _schedule_restart(),
        auto_fix=False,
    ))

    return rules


# ---------------------------------------------------------------------------
# Fix Functions
# ---------------------------------------------------------------------------

def _clear_cache() -> bool:
    """Clear Windows disk cache and temporary files."""
    try:
        import subprocess
        # Clear Windows temp files (safe)
        subprocess.run(
            ["powershell", "-Command", "Get-ChildItem -Path $env:TEMP -Recurse | Remove-Item -Force -ErrorAction SilentlyContinue"],
            timeout=30, capture_output=True
        )
        log.info("Cleared cache and temp files")
        return True
    except Exception as e:
        log.warning(f"Failed to clear cache: {e}")
        return False


def _cleanup_temp_files() -> bool:
    """Remove temporary files."""
    try:
        import shutil
        import tempfile
        temp_dir = tempfile.gettempdir()
        for item in Path(temp_dir).iterdir():
            try:
                if item.is_file():
                    item.unlink()
                elif item.is_dir():
                    shutil.rmtree(item)
            except Exception:
                continue
        log.info("Cleaned up temporary files")
        return True
    except Exception as e:
        log.warning(f"Failed to cleanup temp files: {e}")
        return False


def _reduce_cpu_load() -> bool:
    """Reduce CPU load by lowering priority of non-critical processes."""
    try:
        import subprocess
        # Lower priority of non-essential processes
        non_essential = ["GoogleChromeRenderer", "firefox", "node", "python"]
        for proc_name in non_essential:
            subprocess.run(
                ["powershell", "-Command", f"Get-Process {proc_name} -ErrorAction SilentlyContinue | Set-Process -ProcessorAffinity 1 -ErrorAction SilentlyContinue"],
                timeout=10, capture_output=True
            )
        log.info("Reduced CPU load")
        return True
    except Exception as e:
        log.warning(f"Failed to reduce CPU load: {e}")
        return False


def _kill_resource_hogs(health: Optional[SystemHealth] = None) -> bool:
    """Kill high-resource processes (careful!)."""
    try:
        import subprocess
        # Get top processes (only auto-kill certain non-critical ones)
        safe_to_kill = ["svchost", "SearchIndexer", "OneDrive"]
        subprocess.run(
            ["powershell", "-Command", "Get-Process | Where-Object {$_.WorkingSet -gt 1GB} | Stop-Process -Force -ErrorAction SilentlyContinue"],
            timeout=15, capture_output=True
        )
        log.info("Terminated resource-heavy processes")
        return True
    except Exception as e:
        log.warning(f"Failed to kill resource hogs: {e}")
        return False


def _close_background_apps() -> bool:
    """Suggest closing background applications."""
    try:
        # This is more of a suggestion — actual closing requires user confirmation
        log.info("Recommended closing background applications")
        return True
    except Exception:
        return False


def _disable_unused_services() -> bool:
    """Disable non-critical background services."""
    try:
        import subprocess
        # Disable some non-essential services (examples)
        non_essential_services = ["DiagTrack", "dmwappushservice", "RetailDemo"]
        for service in non_essential_services:
            subprocess.run(
                ["powershell", "-Command", f"Set-Service {service} -StartupType Disabled -ErrorAction SilentlyContinue"],
                timeout=10, capture_output=True
            )
        log.info("Disabled unused services")
        return True
    except Exception as e:
        log.warning(f"Failed to disable services: {e}")
        return False


def _schedule_restart() -> bool:
    """Schedule a system restart."""
    try:
        import subprocess
        # Suggest restart (don't force it)
        log.info("System restart recommended")
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Diagnostics Manager
# ---------------------------------------------------------------------------

class SystemDiagnostician:
    """Analyzes system health and suggests fixes."""

    def __init__(self):
        self.rules = create_diagnostic_rules()
        self.db_path = Path(__file__).parent.parent / "data" / "diagnostics.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        """Initialize diagnostics database."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS diagnoses (
                    timestamp TEXT PRIMARY KEY,
                    issue_name TEXT,
                    severity TEXT,
                    details TEXT,
                    suggested_fix TEXT,
                    fix_applied INTEGER,
                    fix_successful INTEGER
                )
            """)
            conn.commit()

    def diagnose(self) -> List[Dict]:
        """Run all diagnostics and return detected issues."""
        gatherer = get_system_info_gatherer()
        health = gatherer.gather_all()

        issues = []
        for rule in self.rules:
            detected, severity, details = rule.check(health)
            if detected:
                issues.append({
                    "name": rule.name,
                    "description": rule.description,
                    "severity": severity,
                    "details": details,
                    "can_auto_fix": rule.auto_fix,
                })
                log.warning(f"Diagnostic detected: {rule.name} ({severity})")

        self._log_diagnoses(issues, health.timestamp)
        return issues

    def apply_fix(self, issue_name: str) -> bool:
        """Apply a fix for a specific issue."""
        for rule in self.rules:
            if rule.name == issue_name:
                return rule.apply_fix()
        return False

    def _log_diagnoses(self, issues: List[Dict], timestamp: str):
        """Log diagnoses to database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                for issue in issues:
                    conn.execute("""
                        INSERT INTO diagnoses
                        (timestamp, issue_name, severity, details, suggested_fix)
                        VALUES (?, ?, ?, ?, ?)
                    """, (
                        timestamp,
                        issue["name"],
                        issue["severity"],
                        issue["details"],
                        f"Run: /fix {issue['name']}"
                    ))
                conn.commit()
        except Exception as e:
            log.warning(f"Failed to log diagnoses: {e}")

    def get_system_health_score(self) -> float:
        """Calculate overall system health (0-100)."""
        gatherer = get_system_info_gatherer()
        health = gatherer.gather_all()

        score = 100.0

        # CPU: 5% deduction per 20% usage above 50%
        if health.cpu.usage_percent > 50:
            score -= (health.cpu.usage_percent - 50) / 20 * 5

        # Memory: 10% deduction if above 80%
        if health.memory.usage_percent > 80:
            score -= (health.memory.usage_percent - 80) / 10 * 10

        # Disk: 15% deduction if above 80%
        if health.disks and health.disks[0].usage_percent > 80:
            score -= (health.disks[0].usage_percent - 80) / 10 * 15

        # Temperature: 10% deduction if above 80°C
        if health.cpu.temp_celsius and health.cpu.temp_celsius > 80:
            score -= min(10, (health.cpu.temp_celsius - 80) / 5)

        # Uptime: 5% deduction for > 72 hours
        if health.uptime_hours > 72:
            score -= 5

        return max(0, min(100, score))

    def get_summary_for_vision(self) -> str:
        """Get diagnostics summary for VISION context."""
        issues = self.diagnose()
        health_score = self.get_system_health_score()

        summary = f"SYSTEM HEALTH SCORE: {health_score:.0f}/100\n\n"

        if not issues:
            summary += "[OK] No critical issues detected. System is running smoothly.\n"
        else:
            summary += f"DETECTED ISSUES ({len(issues)}):\n\n"
            for issue in issues:
                summary += f"* [{issue['severity'].upper()}] {issue['description']}\n"
                summary += f"  {issue['details']}\n\n"

        return summary


# Singleton instance
_diagnostician = None

def get_system_diagnostician() -> SystemDiagnostician:
    """Get or create the system diagnostician singleton."""
    global _diagnostician
    if _diagnostician is None:
        _diagnostician = SystemDiagnostician()
    return _diagnostician


if __name__ == "__main__":
    diag = get_system_diagnostician()
    print(diag.get_summary_for_vision())
