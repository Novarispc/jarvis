"""
FRIDAY — Scheduled Task Planner Agent

Manages recurring and one-time scheduled tasks.
- Loads schedules from database on startup
- Runs background scheduler checking every minute for due tasks
- Automatically marks tasks as done and regenerates next_run
- Thread-safe integration with JARVIS task system
"""

import logging
import threading
import time
from datetime import datetime, timedelta
from typing import Optional
from pathlib import Path

log = logging.getLogger("jarvis.friday")

# ─────────────────────────────────────────────────────────────────────────────
# Scheduler State
# ─────────────────────────────────────────────────────────────────────────────

_scheduler_thread: Optional[threading.Thread] = None
_scheduler_running = False
_scheduler_lock = threading.Lock()


def _get_db():
    """Get database connection (lazy import to avoid circular deps)."""
    from memory import _get_db as memory_get_db
    return memory_get_db()


def _add_schedule_columns():
    """Add schedule columns to tasks table if they don't exist."""
    try:
        conn = _get_db()
        cursor = conn.cursor()

        # Check if columns exist
        cursor.execute("PRAGMA table_info(tasks)")
        columns = {row[1] for row in cursor.fetchall()}

        alter_cmds = []
        if "schedule_type" not in columns:
            alter_cmds.append("ALTER TABLE tasks ADD COLUMN schedule_type TEXT NULL")
        if "schedule_cron" not in columns:
            alter_cmds.append("ALTER TABLE tasks ADD COLUMN schedule_cron TEXT NULL")
        if "last_run" not in columns:
            alter_cmds.append("ALTER TABLE tasks ADD COLUMN last_run DATETIME NULL")
        if "next_run" not in columns:
            alter_cmds.append("ALTER TABLE tasks ADD COLUMN next_run DATETIME NULL")
        if "is_recurring" not in columns:
            alter_cmds.append("ALTER TABLE tasks ADD COLUMN is_recurring BOOLEAN DEFAULT 0")

        for cmd in alter_cmds:
            try:
                cursor.execute(cmd)
                log.info(f"[FRIDAY] Migration: {cmd}")
            except Exception as e:
                log.debug(f"[FRIDAY] Column may already exist: {e}")

        conn.commit()
        conn.close()
        log.info("[FRIDAY] Database schema ready")
    except Exception as e:
        log.error(f"[FRIDAY] Database migration failed: {e}")


def _parse_time_string(time_str: str) -> Optional[datetime]:
    """Parse time strings like '3pm', '15:30', '3:30 PM' to datetime."""
    if not time_str:
        return None

    time_str = time_str.strip().lower()

    # Handle "Xpm/am" format
    if 'am' in time_str or 'pm' in time_str:
        for fmt in ["%I:%M %p", "%I %p", "%I:%M%p", "%I%p"]:
            try:
                dt = datetime.strptime(time_str, fmt)
                return dt
            except ValueError:
                pass

    # Handle "HH:MM" format
    if ':' in time_str:
        try:
            dt = datetime.strptime(time_str, "%H:%M")
            return dt
        except ValueError:
            pass

    # Handle single hour "3" or "15"
    try:
        hour = int(time_str.split()[0])
        return datetime.strptime(f"{hour:02d}:00", "%H:%M")
    except (ValueError, IndexError):
        pass

    return None


def _calculate_next_run(schedule_type: str, schedule_time: Optional[str] = None) -> Optional[str]:
    """Calculate next_run datetime based on schedule type and current time."""
    if not schedule_type:
        return None

    now = datetime.now()
    next_run = None

    if schedule_type == "daily":
        if schedule_time:
            parsed = _parse_time_string(schedule_time)
            if parsed:
                # Set to today at that time
                next_run = now.replace(hour=parsed.hour, minute=parsed.minute, second=0, microsecond=0)
                # If that time has passed, schedule for tomorrow
                if next_run <= now:
                    next_run += timedelta(days=1)
        else:
            next_run = now + timedelta(days=1)

    elif schedule_type == "weekly":
        next_run = now + timedelta(weeks=1)

    elif schedule_type == "monthly":
        try:
            next_run = (now.replace(day=1) + timedelta(days=32)).replace(day=1)
        except ValueError:
            next_run = now + timedelta(days=30)

    elif schedule_type == "custom":
        # For custom cron, we'd need a cron parser
        # For now, treat as weekly
        next_run = now + timedelta(weeks=1)

    if next_run:
        return next_run.isoformat()

    return None


def create_scheduled_task(
    title: str,
    description: str = "",
    priority: str = "medium",
    schedule_type: str = "daily",
    schedule_time: Optional[str] = None,
    due_date: Optional[str] = None,
    project: str = "",
    tags: str = "[]",
) -> Optional[dict]:
    """Create a new scheduled task. Returns task dict or None on error."""
    try:
        conn = _get_db()
        cursor = conn.cursor()

        now = time.time()
        next_run = _calculate_next_run(schedule_type, schedule_time)
        is_recurring = 1 if schedule_type != "once" else 0

        cursor.execute("""
            INSERT INTO tasks
            (title, description, priority, status, due_date, project, tags,
             created_at, schedule_type, next_run, is_recurring)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            title, description, priority, "open", due_date or "", project, tags,
            now, schedule_type, next_run, is_recurring
        ))

        task_id = cursor.lastrowid
        conn.commit()
        conn.close()

        log.info(f"[FRIDAY] Created scheduled task: {title} (ID: {task_id}, {schedule_type})")

        return {
            "id": task_id,
            "title": title,
            "schedule_type": schedule_type,
            "next_run": next_run,
            "status": "open",
        }

    except Exception as e:
        log.error(f"[FRIDAY] Failed to create scheduled task: {e}")
        return None


def get_scheduled_tasks(only_recurring: bool = False) -> list:
    """Get all scheduled tasks. If only_recurring=True, skip one-time tasks."""
    try:
        conn = _get_db()
        cursor = conn.cursor()

        query = "SELECT * FROM tasks WHERE schedule_type IS NOT NULL AND status != 'cancelled'"
        if only_recurring:
            query += " AND is_recurring = 1"
        query += " ORDER BY next_run ASC"

        cursor.execute(query)
        rows = cursor.fetchall()
        conn.close()

        return rows
    except Exception as e:
        log.error(f"[FRIDAY] Failed to fetch scheduled tasks: {e}")
        return []


def _process_due_task(task_id: int, task_title: str, schedule_type: str, schedule_time: Optional[str] = None):
    """Mark task as done and recalculate next_run if recurring."""
    try:
        conn = _get_db()
        cursor = conn.cursor()

        now = time.time()

        if schedule_type and schedule_type != "once":
            # Recurring task — mark as done and set next_run
            next_run = _calculate_next_run(schedule_type, schedule_time)
            cursor.execute("""
                UPDATE tasks
                SET status = 'done', completed_at = ?, last_run = ?, next_run = ?
                WHERE id = ?
            """, (now, datetime.now().isoformat(), next_run, task_id))
            log.info(f"[FRIDAY] Executed recurring task: {task_title} (next: {next_run})")
        else:
            # One-time task — just mark done
            cursor.execute("""
                UPDATE tasks
                SET status = 'done', completed_at = ?, last_run = ?
                WHERE id = ?
            """, (now, datetime.now().isoformat(), task_id))
            log.info(f"[FRIDAY] Completed scheduled task: {task_title}")

        conn.commit()
        conn.close()

    except Exception as e:
        log.error(f"[FRIDAY] Failed to process due task {task_id}: {e}")


def _scheduler_loop():
    """Background scheduler loop — runs every minute."""
    log.info("[FRIDAY] Scheduler loop started")

    while _scheduler_running:
        try:
            now = datetime.now().isoformat()
            tasks = get_scheduled_tasks()

            for task_row in tasks:
                task_id = task_row[0]
                title = task_row[1]
                next_run = task_row[11] if len(task_row) > 11 else None  # next_run column
                schedule_type = task_row[10] if len(task_row) > 10 else None
                schedule_cron = task_row[9] if len(task_row) > 9 else None
                status = task_row[4]

                # Check if task is due
                if next_run and next_run <= now and status == "open":
                    _process_due_task(task_id, title, schedule_type, schedule_cron)

        except Exception as e:
            log.error(f"[FRIDAY] Scheduler loop error: {e}")

        # Sleep for 60 seconds before next check
        time.sleep(60)


def start_scheduler():
    """Start the background scheduler thread."""
    global _scheduler_thread, _scheduler_running

    with _scheduler_lock:
        if _scheduler_running:
            log.warning("[FRIDAY] Scheduler already running")
            return

        try:
            _add_schedule_columns()
            _scheduler_running = True
            _scheduler_thread = threading.Thread(target=_scheduler_loop, daemon=True)
            _scheduler_thread.start()
            log.info("[FRIDAY] Scheduler started successfully")
        except Exception as e:
            log.error(f"[FRIDAY] Failed to start scheduler: {e}")
            _scheduler_running = False


def stop_scheduler():
    """Stop the background scheduler thread."""
    global _scheduler_running, _scheduler_thread

    with _scheduler_lock:
        _scheduler_running = False
        if _scheduler_thread:
            _scheduler_thread.join(timeout=5)
            log.info("[FRIDAY] Scheduler stopped")
