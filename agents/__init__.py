"""
JARVIS Agents — Specialized AI behaviors and autonomous systems.

Available agents:
- FRIDAY: Scheduled task planner and executor
"""

from .friday import start_scheduler, stop_scheduler, create_scheduled_task, get_scheduled_tasks

__all__ = ["start_scheduler", "stop_scheduler", "create_scheduled_task", "get_scheduled_tasks"]
