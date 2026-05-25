"""
System Information Gatherer for VISION Agent.

Provides comprehensive PC details including hardware, software, processes,
and system health for JARVIS diagnostics and issue resolution.
"""

import json
import logging
import os
import platform
import subprocess
import sqlite3
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import Optional, Dict, List, Any

try:
    import psutil
    PSUTIL_OK = True
except ImportError:
    PSUTIL_OK = False

try:
    import wmi
    WMI_OK = True
except ImportError:
    WMI_OK = False

log = logging.getLogger("jarvis.system_info")

# ---------------------------------------------------------------------------
# Data Classes
# ---------------------------------------------------------------------------

@dataclass
class CPUInfo:
    """CPU information and current usage."""
    brand: str
    cores: int
    threads: int
    max_frequency_ghz: float
    current_frequency_ghz: float
    usage_percent: float
    temp_celsius: Optional[float] = None

@dataclass
class MemoryInfo:
    """Memory (RAM) information."""
    total_gb: float
    used_gb: float
    available_gb: float
    usage_percent: float
    cached_gb: float = 0.0
    buffers_gb: float = 0.0

@dataclass
class DiskInfo:
    """Disk information."""
    drive: str
    total_gb: float
    used_gb: float
    free_gb: float
    usage_percent: float

@dataclass
class ProcessInfo:
    """Running process information."""
    pid: int
    name: str
    memory_mb: float
    cpu_percent: float

@dataclass
class SoftwareInfo:
    """Installed software information."""
    name: str
    version: str
    install_date: Optional[str] = None

@dataclass
class SystemHealth:
    """Overall system health status."""
    timestamp: str
    cpu: CPUInfo
    memory: MemoryInfo
    disks: List[DiskInfo]
    processes: List[ProcessInfo]
    installed_software: List[SoftwareInfo]
    services_summary: Dict[str, int]
    network_connections: int
    uptime_hours: float

# ---------------------------------------------------------------------------
# System Info Gatherer
# ---------------------------------------------------------------------------

class SystemInfoGatherer:
    """Collects comprehensive system information."""

    def __init__(self):
        self.db_path = Path(__file__).parent.parent / "data" / "system_info.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        """Initialize SQLite database for caching system info."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS system_snapshots (
                    timestamp TEXT PRIMARY KEY,
                    cpu_json TEXT,
                    memory_json TEXT,
                    disks_json TEXT,
                    top_processes_json TEXT,
                    installed_software_json TEXT,
                    services_json TEXT,
                    network_json TEXT,
                    uptime_hours REAL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS performance_history (
                    timestamp TEXT PRIMARY KEY,
                    cpu_usage REAL,
                    memory_usage REAL,
                    disk_usage REAL
                )
            """)
            conn.commit()

    def gather_all(self) -> SystemHealth:
        """Gather all system information."""
        timestamp = datetime.now().isoformat()

        cpu_info = self._get_cpu_info()
        memory_info = self._get_memory_info()
        disk_info = self._get_disk_info()
        processes = self._get_top_processes(limit=10)
        software = self._get_installed_software()
        services = self._get_services_summary()
        network = self._get_network_info()
        uptime = self._get_uptime_hours()

        health = SystemHealth(
            timestamp=timestamp,
            cpu=cpu_info,
            memory=memory_info,
            disks=disk_info,
            processes=processes,
            installed_software=software,
            services_summary=services,
            network_connections=network,
            uptime_hours=uptime,
        )

        self._cache_snapshot(health)
        return health

    def _get_cpu_info(self) -> CPUInfo:
        """Get CPU information."""
        if not PSUTIL_OK:
            return CPUInfo(
                brand="Unknown", cores=0, threads=0,
                max_frequency_ghz=0, current_frequency_ghz=0, usage_percent=0
            )

        try:
            freq = psutil.cpu_freq()
            cpu_percent = psutil.cpu_percent(interval=0.5)

            return CPUInfo(
                brand=platform.processor() or "Unknown",
                cores=psutil.cpu_count(logical=False) or 1,
                threads=psutil.cpu_count(logical=True) or 1,
                max_frequency_ghz=freq.max / 1000 if freq else 0,
                current_frequency_ghz=freq.current / 1000 if freq else 0,
                usage_percent=cpu_percent,
                temp_celsius=self._get_cpu_temp()
            )
        except Exception as e:
            log.warning(f"Error getting CPU info: {e}")
            return CPUInfo(
                brand="Unknown", cores=0, threads=0,
                max_frequency_ghz=0, current_frequency_ghz=0, usage_percent=0
            )

    def _get_cpu_temp(self) -> Optional[float]:
        """Get CPU temperature (if available)."""
        try:
            if WMI_OK:
                w = wmi.WMI(namespace="root\\cimv2")
                temps = w.Win32_TemperatureProbe()
                if temps:
                    return float(temps[0].CurrentReading) / 10.0
        except Exception:
            pass

        # Try reading from thermal zone
        try:
            result = subprocess.run(
                ["powershell", "-Command", "Get-WmiObject MSAcpi_ThermalZoneTemperature -Namespace root/wmi | Select-Object CurrentTemperature"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                lines = [l.strip() for l in result.stdout.split('\n') if l.strip() and l[0].isdigit()]
                if lines:
                    temp_raw = int(lines[0])
                    return (temp_raw / 10.0) - 273.15  # Kelvin to Celsius
        except Exception:
            pass

        return None

    def _get_memory_info(self) -> MemoryInfo:
        """Get memory (RAM) information."""
        if not PSUTIL_OK:
            return MemoryInfo(0, 0, 0, 0)

        try:
            mem = psutil.virtual_memory()
            return MemoryInfo(
                total_gb=mem.total / (1024**3),
                used_gb=mem.used / (1024**3),
                available_gb=mem.available / (1024**3),
                usage_percent=mem.percent,
                cached_gb=getattr(mem, 'cached', 0) / (1024**3),
                buffers_gb=getattr(mem, 'buffers', 0) / (1024**3),
            )
        except Exception as e:
            log.warning(f"Error getting memory info: {e}")
            return MemoryInfo(0, 0, 0, 0)

    def _get_disk_info(self) -> List[DiskInfo]:
        """Get disk information for all mounted drives."""
        disks = []
        if not PSUTIL_OK:
            return disks

        try:
            partitions = psutil.disk_partitions(all=False)
            for part in partitions:
                try:
                    usage = psutil.disk_usage(part.mountpoint)
                    disks.append(DiskInfo(
                        drive=part.device,
                        total_gb=usage.total / (1024**3),
                        used_gb=usage.used / (1024**3),
                        free_gb=usage.free / (1024**3),
                        usage_percent=usage.percent,
                    ))
                except Exception:
                    continue
        except Exception as e:
            log.warning(f"Error getting disk info: {e}")

        return disks

    def _get_top_processes(self, limit: int = 10) -> List[ProcessInfo]:
        """Get top processes by memory usage."""
        processes = []
        if not PSUTIL_OK:
            return processes

        try:
            all_procs = []
            for proc in psutil.process_iter(['pid', 'name', 'memory_info', 'cpu_percent']):
                try:
                    all_procs.append(ProcessInfo(
                        pid=proc.info['pid'],
                        name=proc.info['name'],
                        memory_mb=proc.info['memory_info'].rss / (1024**2) if proc.info['memory_info'] else 0,
                        cpu_percent=proc.info['cpu_percent'] or 0,
                    ))
                except Exception:
                    continue

            # Sort by memory usage and return top N
            all_procs.sort(key=lambda p: p.memory_mb, reverse=True)
            return all_procs[:limit]
        except Exception as e:
            log.warning(f"Error getting processes: {e}")
            return []

    def _get_installed_software(self) -> List[SoftwareInfo]:
        """Get list of installed software (Windows programs)."""
        software = []
        if not WMI_OK:
            return software

        try:
            w = wmi.WMI()
            products = w.Win32_Product()
            for prod in products[:20]:  # Limit to 20 most recent
                try:
                    software.append(SoftwareInfo(
                        name=prod.Name or "Unknown",
                        version=prod.Version or "Unknown",
                        install_date=prod.InstallDate,
                    ))
                except Exception:
                    continue
        except Exception as e:
            log.warning(f"Error getting installed software: {e}")

        # Fallback: try registry
        if not software:
            software = self._get_software_from_registry()

        return software[:30]  # Limit to 30 total

    def _get_software_from_registry(self) -> List[SoftwareInfo]:
        """Get installed software from Windows registry."""
        software = []
        try:
            result = subprocess.run(
                ["powershell", "-Command",
                 "Get-ItemProperty HKLM:\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\* | "
                 "Select-Object DisplayName, DisplayVersion | ConvertTo-Json"],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                apps = json.loads(result.stdout)
                if isinstance(apps, list):
                    for app in apps:
                        if app.get('DisplayName'):
                            software.append(SoftwareInfo(
                                name=app['DisplayName'],
                                version=app.get('DisplayVersion', 'Unknown')
                            ))
        except Exception as e:
            log.warning(f"Error reading software from registry: {e}")

        return software

    def _get_services_summary(self) -> Dict[str, int]:
        """Get summary of Windows services."""
        summary = {"total": 0, "running": 0, "stopped": 0}
        if not WMI_OK:
            return summary

        try:
            w = wmi.WMI()
            services = w.Win32_Service()
            summary["total"] = len(services)
            summary["running"] = sum(1 for s in services if s.State == "Running")
            summary["stopped"] = summary["total"] - summary["running"]
        except Exception as e:
            log.warning(f"Error getting services: {e}")

        return summary

    def _get_network_info(self) -> int:
        """Get active network connections count."""
        if not PSUTIL_OK:
            return 0

        try:
            connections = psutil.net_connections()
            return sum(1 for c in connections if c.status == 'ESTABLISHED')
        except Exception:
            return 0

    def _get_uptime_hours(self) -> float:
        """Get system uptime in hours."""
        if not PSUTIL_OK:
            return 0

        try:
            boot_time = psutil.boot_time()
            return (datetime.now() - datetime.fromtimestamp(boot_time)).total_seconds() / 3600
        except Exception:
            return 0

    def _cache_snapshot(self, health: SystemHealth):
        """Cache system health snapshot in database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO system_snapshots
                    (timestamp, cpu_json, memory_json, disks_json, top_processes_json,
                     installed_software_json, services_json, network_json, uptime_hours)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    health.timestamp,
                    json.dumps(asdict(health.cpu)),
                    json.dumps(asdict(health.memory)),
                    json.dumps([asdict(d) for d in health.disks]),
                    json.dumps([asdict(p) for p in health.processes]),
                    json.dumps([asdict(s) for s in health.installed_software]),
                    json.dumps(health.services_summary),
                    json.dumps({"connections": health.network_connections}),
                    health.uptime_hours,
                ))

                # Also cache performance metrics
                conn.execute("""
                    INSERT OR REPLACE INTO performance_history
                    (timestamp, cpu_usage, memory_usage, disk_usage)
                    VALUES (?, ?, ?, ?)
                """, (
                    health.timestamp,
                    health.cpu.usage_percent,
                    health.memory.usage_percent,
                    health.disks[0].usage_percent if health.disks else 0,
                ))
                conn.commit()
        except Exception as e:
            log.warning(f"Error caching system snapshot: {e}")

    def get_system_summary(self) -> str:
        """Get a human-readable system summary for VISION context."""
        health = self.gather_all()

        temp_str = f"{health.cpu.temp_celsius:.1f}°C" if health.cpu.temp_celsius else "Not available"
        summary = f"""
SYSTEM INFORMATION SNAPSHOT ({health.timestamp})

HARDWARE:
• CPU: {health.cpu.brand}
  - Cores: {health.cpu.cores} cores / {health.cpu.threads} threads
  - Frequency: {health.cpu.current_frequency_ghz:.2f} GHz (max: {health.cpu.max_frequency_ghz:.2f} GHz)
  - Usage: {health.cpu.usage_percent:.1f}%
  - Temperature: {temp_str}

• Memory: {health.memory.total_gb:.1f} GB total
  - Used: {health.memory.used_gb:.1f} GB ({health.memory.usage_percent:.1f}%)
  - Available: {health.memory.available_gb:.1f} GB
  - Cached: {health.memory.cached_gb:.1f} GB

STORAGE:
"""
        for disk in health.disks:
            summary += f"• {disk.drive}: {disk.total_gb:.0f} GB total, {disk.used_gb:.0f} GB used ({disk.usage_percent:.1f}%)\n"

        summary += f"""
TOP PROCESSES (by memory):
"""
        for proc in health.processes[:5]:
            summary += f"• {proc.name} (PID {proc.pid}): {proc.memory_mb:.0f} MB, {proc.cpu_percent:.1f}% CPU\n"

        summary += f"""
SYSTEM STATUS:
• Uptime: {health.uptime_hours:.1f} hours
• Services: {health.services_summary['running']}/{health.services_summary['total']} running
• Network Connections: {health.network_connections} active

INSTALLED SOFTWARE (sample - {len(health.installed_software)} total):
"""
        for soft in health.installed_software[:5]:
            summary += f"• {soft.name} v{soft.version}\n"

        return summary

    def get_diagnostics_context(self) -> Dict[str, Any]:
        """Get detailed diagnostics data for VISION."""
        health = self.gather_all()
        return {
            "timestamp": health.timestamp,
            "cpu": asdict(health.cpu),
            "memory": asdict(health.memory),
            "disks": [asdict(d) for d in health.disks],
            "top_processes": [asdict(p) for p in health.processes],
            "installed_software": [asdict(s) for s in health.installed_software],
            "services": health.services_summary,
            "network_connections": health.network_connections,
            "uptime_hours": health.uptime_hours,
        }


# Singleton instance
_gatherer = None

def get_system_info_gatherer() -> SystemInfoGatherer:
    """Get or create the system info gatherer singleton."""
    global _gatherer
    if _gatherer is None:
        _gatherer = SystemInfoGatherer()
    return _gatherer


if __name__ == "__main__":
    gatherer = get_system_info_gatherer()
    summary = gatherer.get_system_summary()
    print(summary)
