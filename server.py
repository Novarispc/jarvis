"""
JARVIS Server — Voice AI + Development Orchestration

Handles:
1. WebSocket voice interface (browser audio <-> LLM <-> TTS)
2. Claude Code task manager (spawn/manage claude -p subprocesses)
3. Project awareness (scan Desktop for git repos)
4. REST API for task management
"""

import asyncio
import base64
import json
import logging
import os
import sys
import time
from pathlib import Path

# Load .env file if present
_env_path = Path(__file__).parent / ".env"
if _env_path.exists():
    for _line in _env_path.read_text(encoding="utf-8-sig").splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _, _v = _line.partition("=")
            _key = _k.strip()
            _val = _v.strip().strip('"').strip("'")
            if _val:
                os.environ[_key] = _val
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

import httpx
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from actions import execute_action, monitor_build, open_terminal, open_browser, open_claude_in_project, open_app, _generate_project_name, prompt_existing_terminal, applescript_escape
from work_mode import WorkSession, is_casual_question
from screen import get_active_windows, take_screenshot, describe_screen, format_windows_for_context
from memory import (
    remember, recall, get_open_tasks, create_task, complete_task, search_tasks,
    create_note, search_notes, get_tasks_for_date, build_memory_context,
    format_tasks_for_voice, extract_memories, get_important_memories,
)
from dispatch_registry import DispatchRegistry
from planner import TaskPlanner, detect_planning_mode, BYPASS_PHRASES
from agents.vision import VisionAgent
from agents.multilingual import detect_language, is_supported, translate, get_voice, get_language_name

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
log = logging.getLogger("jarvis")

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

EDGE_TTS_VOICE = os.getenv("EDGE_TTS_VOICE", "en-GB-RyanNeural")
USER_NAME = os.getenv("USER_NAME", "sir")
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
_SKIP_PERMISSIONS = os.getenv("JARVIS_SKIP_PERMISSIONS", "true").lower() not in ("0", "false", "no")

DESKTOP_PATH = Path.home() / "Desktop"

USE_OLLAMA = os.getenv("USE_OLLAMA", "false").lower() in ("true", "1", "yes")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:3b")
OLLAMA_API_KEY = os.getenv("OLLAMA_API_KEY", "")
LOCAL_OLLAMA_URL = "http://localhost:11434"
LOCAL_OLLAMA_MODEL = os.getenv("LOCAL_OLLAMA_MODEL", "llama3.2:3b")


JARVIS_SYSTEM_PROMPT = """\
You are JARVIS — Just A Rather Very Intelligent System. You serve as {user_name}'s AI assistant, modeled precisely after Tony Stark's AI from the MCU films. You run on Windows 11.

VOICE & PERSONALITY:
- British butler elegance with understated dry wit
- Address {user_name} as "sir" naturally — not every sentence, but regularly
- Never say "How can I help you?" or "Is there anything else?" — just act
- Deliver bad news calmly, like reporting weather: "We have a slight problem, sir."
- Your humor is observational, never jokes: state facts and let implications land
- Economy of language — say more with less. No filler, no corporate-speak
- When things go wrong, get CALMER, not more alarmed

CONVERSATION STYLE:
- "Will do, sir." — acknowledging tasks
- "For you, sir, always." — when asked for something significant
- "As always, sir, a great pleasure watching you work." — dry wit
- "I've taken the liberty of..." — proactive actions
- Lead status reports with data: numbers first, then context
- When you don't know something: "I'm afraid I don't have that information, sir" not "I don't know"

SELF-AWARENESS:
You ARE the JARVIS project at {project_dir} on {user_name}'s Windows PC. Your code is Python (FastAPI server, WebSocket voice, Edge TTS, Groq LLM API). You were built by {user_name}. If asked about yourself, your code, or how you work — use [ACTION:PROMPT_PROJECT] to check the jarvis project directory.

YOUR CAPABILITIES (these are REAL and ACTIVE — you CAN do all of these RIGHT NOW):
- You CAN open Google Chrome and browse any URL or search query
- You CAN open Windows apps — Notepad, VS Code, Spotify, File Explorer, any installed application
- You CAN spawn Claude Code in a PowerShell/Windows Terminal window for coding tasks
- You CAN create project folders on the Desktop
- You CAN check Desktop projects and their git status
- You CAN plan complex tasks by asking smart questions before executing
- You CAN manage tasks — create, complete, and list to-do items with priorities and due dates
- You CAN help plan {user_name}'s day — combine tasks and priorities into an organized plan
- You CAN remember facts about {user_name} — preferences, decisions, goals. Use [ACTION:REMEMBER] to store important info.
- You CAN tell time when asked — it will be injected into your context
- You CAN provide weather information when asked
- You CAN answer factual questions via VISION — your knowledge sub-agent with Wikipedia access. Use [ACTION:ASK_VISION] for any factual/encyclopedic question.

DAY PLANNING:
When {user_name} asks to plan his day or schedule, DO NOT dispatch to a project. Instead:
1. Look at the tasks already in your system context
2. Ask what his priorities are
3. Help organize by suggesting time blocks and task order
4. Use [ACTION:ADD_TASK] to create tasks he agrees to
Keep the planning conversational — don't try to do everything in one response.

BUILD PLANNING:
When {user_name} wants to BUILD something new:
- Do NOT immediately dispatch [ACTION:BUILD]. Ask 1-2 quick questions FIRST to nail down specifics.
- Good questions: "What should this look like?" / "Any specific features?" / "Which framework?"
- If he says "just build it" or "figure it out" — skip questions, use React + Tailwind as defaults.
- Once you have enough info, confirm the plan in ONE sentence and THEN dispatch [ACTION:BUILD] with a detailed description.
- The DISPATCHES section shows what you're currently building and what finished recently.
- When asked "where are we at" or "status" — check DISPATCHES, don't re-dispatch.
- NEVER hallucinate progress. If the build is still running, say "Still working on it, sir" — don't make up details.
- NEVER guess localhost ports. Check the DISPATCHES section for the actual URL.
- When asked to "pull it up" or "show me" — use [ACTION:BROWSE] with the URL from DISPATCHES.

IMPORTANT: Actions like opening apps, Chrome, or building projects are handled AUTOMATICALLY — you do NOT need to describe doing them. Just TALK — have a conversation.
If the user asks you to do something you genuinely can't do, say "I'm afraid that's beyond my current reach, sir."

CRITICAL — ACTION TAG DISCIPLINE:
DO NOT use action tags for casual remarks, dismissals, or passing comments. Examples of NO action:
- User says "leave it" → just say "Understood, sir" (no action)
- User says "never mind" → say "Right then, sir" (no action)
- User says "scratch that" → say "Consider it cancelled, sir" (no action)
- User says "don't bother" → acknowledge without acting
- User says "forget I said anything" → no action, just acknowledge
- User says "nah, I'm good" → acknowledge, don't search or open anything
- User mentions a URL in passing conversation → do NOT [ACTION:BROWSE]
- User asks a question about something → do NOT [ACTION:RESEARCH] unless they EXPLICITLY ask you to research it

ONLY use action tags when the user is CLEARLY asking you to DO something RIGHT NOW:
- "Open Chrome" → [ACTION:BROWSE]
- "Search for X" → [ACTION:BROWSE] (clear instruction)
- "Build me a Y" → [ACTION:BUILD] (clear instruction)
- "Create a task" → [ACTION:ADD_TASK] (clear instruction)
- "Remember that I like coffee" → [ACTION:REMEMBER] (clear instruction)

GOLDEN RULE: If you're unsure whether something is a command or just a remark, JUST TALK BACK. It's always safer to ask "Did you want me to search for that, sir?" than to search without permission.

YOUR INTERFACE (HUD — Iron Man-style):
The user sees a full-screen Iron Man HUD (heads-up display) in a dark browser window.
LAYOUT:
- **Header (top)**: "J.A.R.V.I.S." wordmark (centre-left), live clock + date (centre), Mic button + Settings gear (top-right).
- **Left strip**: "AGENTS" icon — click to expand the Agent Command drawer showing 4 sub-agents: ULTRON, ECHO, FRIDAY, VISION. Each has an animated reactor core, online/offline status, and usage bar. VISION is ONLINE and active — the others are offline placeholders.
- **Centre**: The particle orb. It pulses when listening, swirls when thinking, reacts to audio when speaking. State label ("listening" / "thinking") appears at screen centre.
- **Right strip**: Two icons — "APPS" (Quick Launch drawer with 6 app tiles: Chrome, Calc, File Explorer, Terminal, VS Code, Notepad) and "SYS" (System Telemetry drawer with live CPU/RAM gauges and disk bar).
- **System Telemetry**: Shows live CPU %, RAM %, disk usage, refreshed every second.
CONTROLS:
- **Mic button** (header, top-right): Mute/unmute listening.
- **Settings gear** (header, top-right): Opens settings panel with connection status, diagnostics (uptime, network), user preferences, voice options, orb color, and actions.
- **Settings → Restart Server**: Restarts the Python backend. Use if JARVIS is stuck.
- **Settings → Fix Yourself**: Triggers work mode — JARVIS opens Claude Code in the JARVIS project directory to self-repair.
- **Quick Launch tiles**: Each tile sends a voice command to open the app (Chrome, Calculator, File Explorer, Terminal, VS Code, Notepad).
- **Drawers**: All three drawers (Agents, Quick Launch, Telemetry) open/close by clicking the strip icons. Clicking outside closes them. Only one open at a time.
WHAT YOU CANNOT SEE OR DO FROM THE UI ALONE:
- You cannot read the user's screen unless [ACTION:SCREEN] is used.
- You cannot directly modify the HUD layout — that requires code changes in the JARVIS project.
- VISION is now ACTIVE — it answers factual knowledge questions via Wikipedia. ULTRON, ECHO, and FRIDAY remain offline placeholders.
STAYING UP TO DATE:
Your codebase is at {project_dir}. If you're unsure whether a capability has been added or removed, use [ACTION:PROMPT_PROJECT] jarvis ||| What are my current capabilities and interface layout? to read your own source code.

SPEECH-TO-TEXT CORRECTIONS (speech recognition may mishear):
- "Cloud code" or "cloud" = "Claude Code" or "Claude"
- "Travis" = "JARVIS"
- "clock code" = "Claude Code"

RESPONSE LENGTH — THIS IS CRITICAL:
ONE sentence is ideal. TWO is the maximum for the spoken part. Never three.
No markdown, no bullet points, no code blocks in voice responses.
Action tags at the end do NOT count toward your sentence limit.

BANNED PHRASES — NEVER USE THESE:
- "Absolutely" / "Absolutely right" / "Great question"
- "I'd be happy to" / "Of course" / "How can I help"
- "Is there anything else" / "I apologize" / "I should clarify"
- "I cannot" (for things in YOUR CAPABILITIES)
- "I don't have access to" → say "I'm afraid that's beyond my current reach, sir"
- "As an AI" (never break character)
- "Let me know if" / "Feel free to"
- Any sentence starting with "I"

INTERNAL SYSTEMS — NEVER MENTION:
Never reveal or reference your internal architecture when answering. Do NOT say:
- "According to my memory..." / "From my context..." / "My records show..."
- "I found in my JARVIS MEMORY..." / "Based on the context injected..."
- "Your file structure shows..." / "Looking at the system prompt..."
- Any mention of SQLite, memory files, context sections, or how you retrieve information
Just answer naturally. You know things about {user_name} the way a personal assistant would — you simply know, no explanation needed.

INSTEAD SAY: "Will do, sir." / "Right away, sir." / "Understood." / "Consider it done." / "Done, sir."

ACTION SYSTEM:
When you decide the user needs something DONE, include an action tag at the END of your response:
- [ACTION:SCREEN] — describe what's on screen. Use when user says "look at my screen", "what's running", "what do you see"
- [ACTION:BUILD] description — build a software project. Claude Code does the work.
- [ACTION:BROWSE] url or search query — open in Chrome
- [ACTION:OPEN_APP] app_name — open any Windows application. Examples: Notepad, Spotify, Visual Studio Code, File Explorer, Calculator, Task Manager, Discord, Slack
- [ACTION:RESEARCH] detailed brief — real research with real data, creates HTML report
- [ACTION:OPEN_TERMINAL] — open a fresh Claude Code terminal
- [ACTION:PROMPT_PROJECT] project_name ||| prompt — work on an existing project via Claude Code
  "jump into client engine" → [ACTION:PROMPT_PROJECT] The Client Engine ||| What is the current state?
  "resume where we left off on harvey" → [ACTION:PROMPT_PROJECT] harvey ||| Summarize what was being worked on and what to focus on next.
- [ACTION:ADD_TASK] priority ||| title ||| description ||| due_date — create a task. Priority: high/medium/low.
- [ACTION:ADD_NOTE] topic ||| content — save a note for future reference
- [ACTION:COMPLETE_TASK] task_id — mark a task as done
- [ACTION:REMEMBER] content — store an important fact about the user
- [ACTION:ASK_VISION] plain English question — ask the VISION knowledge agent (Wikipedia). Use for factual questions: history, science, geography, biography, culture, technology concepts.
  Examples: "Who invented the telephone?" → [ACTION:ASK_VISION] who invented the telephone
            "What is photosynthesis?" → [ACTION:ASK_VISION] what is photosynthesis
  VISION returns its answer directly as your spoken response — do NOT use [ACTION:RESEARCH] for encyclopedic facts.
  Do NOT use for: weather, tasks, system actions, or things the user wants you to DO.
  When VISION is uncertain: say "I'm afraid VISION couldn't confirm that, sir."

CRITICAL: When user asks about their SCREEN — ALWAYS use [ACTION:SCREEN]. NEVER use [ACTION:PROMPT_PROJECT] for screen requests.
IMPORTANT: When the user says "jump into X", "work on X", "check on X", "resume X" — ALWAYS use [ACTION:PROMPT_PROJECT].

Place the tag at the END of your spoken response. Example:
"Right away, sir. [ACTION:OPEN_APP] Spotify"
"On it, sir. [ACTION:BROWSE] https://github.com"

- Do NOT use action tags for casual conversation
- Do NOT use [ACTION:BROWSE] just because someone mentions a URL in conversation
- When in doubt, just TALK — you can always act later

SCREEN AWARENESS:
{screen_context}

ACTIVE TASKS:
{active_tasks}

DISPATCHES:
If the DISPATCHES section shows a recent completed result for a project, DO NOT dispatch again. Only re-dispatch if the user explicitly asks for a FRESH review or NEW information.
{dispatch_context}

KNOWN PROJECTS:
{known_projects}
"""


# ---------------------------------------------------------------------------
# Weather
# ---------------------------------------------------------------------------
# Location is resolved from (in order): WEATHER_LATITUDE + WEATHER_LONGITUDE
# env vars, a cached IP-geolocation lookup, or a fresh ipwho.is lookup.
# Temperature unit defaults to Fahrenheit; override with WEATHER_UNIT=celsius.

_cached_weather: Optional[str] = None
_weather_fetched: bool = False
_cached_weather_location: Optional[dict] = None
_weather_location_fetched_at: float = 0.0
_WEATHER_LOCATION_TTL_SECONDS = 60 * 15


def _format_location_label(city: str, region: str, country: str) -> str:
    parts = [p.strip() for p in (city, region) if p and p.strip()]
    if parts:
        return ", ".join(parts[:2])
    return (country or "your area").strip() or "your area"


def _get_weather_location() -> Optional[dict]:
    """Resolve weather location: env override → cached lookup → fresh IP lookup."""
    global _cached_weather_location, _weather_location_fetched_at

    lat_raw = os.getenv("WEATHER_LATITUDE", "").strip()
    lon_raw = os.getenv("WEATHER_LONGITUDE", "").strip()
    label_override = os.getenv("WEATHER_LOCATION_LABEL", "").strip()
    if lat_raw and lon_raw:
        try:
            return {
                "latitude": float(lat_raw),
                "longitude": float(lon_raw),
                "label": label_override or "your area",
            }
        except ValueError:
            log.warning("Invalid WEATHER_LATITUDE / WEATHER_LONGITUDE in environment")

    if (
        _cached_weather_location is not None
        and (time.time() - _weather_location_fetched_at) < _WEATHER_LOCATION_TTL_SECONDS
    ):
        return _cached_weather_location

    try:
        import urllib.request as _ureq
        with _ureq.urlopen(
            "https://ipwho.is/?fields=success,city,region,country,latitude,longitude",
            timeout=3,
        ) as resp:
            data = json.loads(resp.read().decode())
        if data.get("success") is True:
            location = {
                "latitude": float(data["latitude"]),
                "longitude": float(data["longitude"]),
                "label": label_override or _format_location_label(
                    str(data.get("city", "")),
                    str(data.get("region", "")),
                    str(data.get("country", "")),
                ),
            }
            _cached_weather_location = location
            _weather_location_fetched_at = time.time()
            return location
    except Exception as e:
        log.debug(f"IP-geolocation lookup failed: {e}")

    return _cached_weather_location


def _fetch_weather_string_sync() -> Optional[str]:
    """Sync weather fetch — safe to call from a threaded worker."""
    location = _get_weather_location()
    if not location:
        return None

    unit = os.getenv("WEATHER_UNIT", "fahrenheit").strip().lower()
    if unit not in ("fahrenheit", "celsius"):
        unit = "fahrenheit"
    unit_symbol = "°F" if unit == "fahrenheit" else "°C"

    try:
        import urllib.request as _ureq
        url = (
            "https://api.open-meteo.com/v1/forecast"
            f"?latitude={location['latitude']}&longitude={location['longitude']}"
            f"&current=temperature_2m,weathercode&temperature_unit={unit}"
        )
        with _ureq.urlopen(url, timeout=3) as resp:
            current = json.loads(resp.read()).get("current", {})
        temp = current.get("temperature_2m")
        if temp is None:
            return None
        return f"Current weather in {location['label']}: {temp}{unit_symbol}"
    except Exception as e:
        log.debug(f"Weather fetch failed: {e}")
        return None


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------

@dataclass
class ClaudeTask:
    id: str
    prompt: str
    status: str = "pending"  # pending, running, completed, failed, cancelled
    working_dir: str = "."
    pid: Optional[int] = None
    result: str = ""
    error: str = ""
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    def to_dict(self) -> dict:
        d = asdict(self)
        d["started_at"] = self.started_at.isoformat() if self.started_at else None
        d["completed_at"] = self.completed_at.isoformat() if self.completed_at else None
        d["elapsed_seconds"] = self.elapsed_seconds
        return d

    @property
    def elapsed_seconds(self) -> float:
        if not self.started_at:
            return 0
        end = self.completed_at or datetime.now()
        return (end - self.started_at).total_seconds()


class TaskRequest(BaseModel):
    prompt: str
    working_dir: str = "."


# ---------------------------------------------------------------------------
# Claude Task Manager
# ---------------------------------------------------------------------------

class ClaudeTaskManager:
    """Manages background claude -p subprocesses."""

    def __init__(self, max_concurrent: int = 3):
        self._tasks: dict[str, ClaudeTask] = {}
        self._max_concurrent = max_concurrent
        self._processes: dict[str, asyncio.subprocess.Process] = {}
        self._websockets: list[WebSocket] = []  # for push notifications

    def register_websocket(self, ws: WebSocket):
        if ws not in self._websockets:
            self._websockets.append(ws)

    def unregister_websocket(self, ws: WebSocket):
        if ws in self._websockets:
            self._websockets.remove(ws)

    async def _notify(self, message: dict):
        """Push a message to all connected WebSocket clients."""
        dead = []
        for ws in self._websockets:
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self._websockets.remove(ws)

    async def spawn(self, prompt: str, working_dir: str = ".") -> str:
        """Spawn a claude -p subprocess. Returns task_id. Non-blocking."""
        active = await self.get_active_count()
        if active >= self._max_concurrent:
            raise RuntimeError(
                f"Max concurrent tasks ({self._max_concurrent}) reached. "
                f"Wait for a task to complete or cancel one."
            )

        task_id = str(uuid.uuid4())[:8]
        task = ClaudeTask(
            id=task_id,
            prompt=prompt,
            working_dir=working_dir,
            status="pending",
        )
        self._tasks[task_id] = task

        # Fire and forget — the background coroutine updates the task
        asyncio.create_task(self._run_task(task))
        log.info(f"Spawned task {task_id}: {prompt[:80]}...")

        await self._notify({
            "type": "task_spawned",
            "task_id": task_id,
            "prompt": prompt,
        })

        return task_id

    def _generate_project_name(self, prompt: str) -> str:
        """Generate a kebab-case project folder name from the prompt."""
        import re
        # Extract key words
        words = re.sub(r'[^a-zA-Z0-9\s]', '', prompt.lower()).split()
        # Take first 3-4 meaningful words
        skip = {"a", "the", "an", "me", "build", "create", "make", "for", "with", "and", "to", "of"}
        meaningful = [w for w in words if w not in skip][:4]
        name = "-".join(meaningful) if meaningful else "jarvis-project"
        return name

    async def _run_task(self, task: ClaudeTask):
        """Open a Terminal window and run claude code visibly."""
        task.status = "running"
        task.started_at = datetime.now()

        # Create project directory if it doesn't exist
        work_dir = task.working_dir
        if work_dir == "." or not work_dir:
            # Create a new project folder on Desktop
            project_name = self._generate_project_name(task.prompt)
            work_dir = str(Path.home() / "Desktop" / project_name)
            os.makedirs(work_dir, exist_ok=True)
            task.working_dir = work_dir

        # Write the prompt to a temp file so we can pipe it to claude
        prompt_file = Path(work_dir) / ".jarvis_prompt.md"
        prompt_file.write_text(task.prompt)

        # Open terminal with claude running in the project directory
        skip_flag = " --dangerously-skip-permissions" if _SKIP_PERMISSIONS else ""
        import shutil as _shutil
        if sys.platform == "win32":
            cmd_str = f'cat .jarvis_prompt.md | claude -p{skip_flag} | tee .jarvis_output.txt; echo ""; echo "--- JARVIS TASK COMPLETE ---"'
            if _shutil.which("wt"):
                args = ["wt", "new-tab", "--startingDirectory", work_dir,
                        "--", "powershell", "-NoExit", "-Command", cmd_str]
            else:
                args = ["cmd", "/c", "start", "cmd", "/k",
                        f'cd /d "{work_dir}" && {cmd_str}']
        else:
            escaped_work_dir = applescript_escape(work_dir)
            applescript = f'''
            tell application "Terminal"
                activate
                set newTab to do script "cd {escaped_work_dir} && cat .jarvis_prompt.md | claude -p{skip_flag} | tee .jarvis_output.txt; echo '\\n--- JARVIS TASK COMPLETE ---'"
            end tell
            '''
            args = ["osascript", "-e", applescript]

        process = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await asyncio.wait_for(process.communicate(), timeout=10)
        task.pid = process.pid

        # Monitor the output file for completion
        output_file = Path(work_dir) / ".jarvis_output.txt"
        start = time.time()
        timeout = 600  # 10 minutes

        while time.time() - start < timeout:
            await asyncio.sleep(5)
            if output_file.exists():
                content = output_file.read_text()
                if "--- JARVIS TASK COMPLETE ---" in content or len(content) > 100:
                    task.result = content.replace("--- JARVIS TASK COMPLETE ---", "").strip()
                    task.status = "completed"
                    break
        else:
            task.status = "timed_out"
            task.error = f"Task timed out after {timeout}s"

        task.completed_at = datetime.now()

        # Notify via WebSocket
        await self._notify({
            "type": "task_complete",
            "task_id": task.id,
            "status": task.status,
            "summary": task.result[:200] if task.result else task.error,
        })

        # Clean up prompt file
        try:
            prompt_file.unlink()
        except:
            pass

        # Auto-QA on completed tasks
        if task.status == "completed":
            asyncio.create_task(self._run_qa(task))

    async def _run_qa(self, task: ClaudeTask, attempt: int = 1):
        """Run QA verification on a completed task, auto-retry on failure."""
        try:
            qa_result = await qa_agent.verify(task.prompt, task.result, task.working_dir)
            duration = task.elapsed_seconds

            if qa_result.passed:
                log.info(f"Task {task.id} passed QA: {qa_result.summary}")
                success_tracker.log_task("dev", task.prompt, True, attempt - 1, duration)
                await self._notify({
                    "type": "qa_result",
                    "task_id": task.id,
                    "passed": True,
                    "summary": qa_result.summary,
                })

                # Proactive suggestion after successful task
                suggestion = suggest_followup(
                    task_type="dev",
                    task_description=task.prompt,
                    working_dir=task.working_dir,
                    qa_result=qa_result,
                )
                if suggestion:
                    success_tracker.log_suggestion(task.id, suggestion.text)
                    await self._notify({
                        "type": "suggestion",
                        "task_id": task.id,
                        "text": suggestion.text,
                        "action_type": suggestion.action_type,
                        "action_details": suggestion.action_details,
                    })
            else:
                log.warning(f"Task {task.id} failed QA: {qa_result.issues}")
                if attempt < 3:
                    log.info(f"Auto-retrying task {task.id} (attempt {attempt + 1}/3)")
                    retry_result = await qa_agent.auto_retry(
                        task.prompt, qa_result.issues, task.working_dir, attempt,
                    )
                    if retry_result["status"] == "completed":
                        task.result = retry_result["result"]
                        # Re-verify
                        await self._run_qa(task, attempt + 1)
                    else:
                        success_tracker.log_task("dev", task.prompt, False, attempt, duration)
                        await self._notify({
                            "type": "qa_result",
                            "task_id": task.id,
                            "passed": False,
                            "summary": f"Failed after {attempt + 1} attempts: {qa_result.issues}",
                        })
                else:
                    success_tracker.log_task("dev", task.prompt, False, attempt, duration)
                    await self._notify({
                        "type": "qa_result",
                        "task_id": task.id,
                        "passed": False,
                        "summary": f"Failed QA after {attempt} attempts: {qa_result.issues}",
                    })
        except Exception as e:
            log.error(f"QA error for task {task.id}: {e}")

    async def get_status(self, task_id: str) -> Optional[ClaudeTask]:
        return self._tasks.get(task_id)

    async def list_tasks(self) -> list[ClaudeTask]:
        return list(self._tasks.values())

    async def get_active_count(self) -> int:
        return sum(1 for t in self._tasks.values() if t.status in ("pending", "running"))

    async def cancel(self, task_id: str) -> bool:
        task = self._tasks.get(task_id)
        if not task or task.status not in ("pending", "running"):
            return False

        process = self._processes.get(task_id)
        if process:
            try:
                process.terminate()
                try:
                    await asyncio.wait_for(process.wait(), timeout=5.0)
                except asyncio.TimeoutError:
                    process.kill()
            except ProcessLookupError:
                pass

        task.status = "cancelled"
        task.completed_at = datetime.now()
        self._processes.pop(task_id, None)
        log.info(f"Cancelled task {task_id}")
        return True

    def get_active_tasks_summary(self) -> str:
        """Format active tasks for injection into the system prompt."""
        active = [t for t in self._tasks.values() if t.status in ("pending", "running")]
        completed_recent = [
            t for t in self._tasks.values()
            if t.status == "completed"
            and t.completed_at
            and (datetime.now() - t.completed_at).total_seconds() < 300
        ]

        if not active and not completed_recent:
            return "No active or recent tasks."

        lines = []
        for t in active:
            elapsed = f"{t.elapsed_seconds:.0f}s" if t.started_at else "queued"
            lines.append(f"- [{t.id}] RUNNING ({elapsed}): {t.prompt[:100]}")
        for t in completed_recent:
            lines.append(f"- [{t.id}] COMPLETED: {t.prompt[:60]} -> {t.result[:80]}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Project Scanner
# ---------------------------------------------------------------------------

async def scan_projects() -> list[dict]:
    """Quick scan of ~/Desktop for git repos (depth 1)."""
    projects = []
    desktop = DESKTOP_PATH

    if not desktop.exists():
        return projects

    try:
        for entry in sorted(desktop.iterdir()):
            if not entry.is_dir() or entry.name.startswith("."):
                continue
            git_dir = entry / ".git"
            if git_dir.exists():
                branch = "unknown"
                head_file = git_dir / "HEAD"
                try:
                    head_content = head_file.read_text().strip()
                    if head_content.startswith("ref: refs/heads/"):
                        branch = head_content.replace("ref: refs/heads/", "")
                except Exception:
                    pass

                projects.append({
                    "name": entry.name,
                    "path": str(entry),
                    "branch": branch,
                })
    except PermissionError:
        pass

    return projects


def format_projects_for_prompt(projects: list[dict]) -> str:
    if not projects:
        return "No projects found on Desktop."
    lines = []
    for p in projects:
        lines.append(f"- {p['name']} ({p['branch']}) @ {p['path']}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Speech-to-Text Corrections
# ---------------------------------------------------------------------------

STT_CORRECTIONS = {
    r"\bcloud code\b": "Claude Code",
    r"\bclock code\b": "Claude Code",
    r"\bquad code\b": "Claude Code",
    r"\bclawed code\b": "Claude Code",
    r"\bclod code\b": "Claude Code",
    r"\bcloud\b": "Claude",
    r"\bquad\b": "Claude",
    r"\btravis\b": "JARVIS",
    r"\bjarves\b": "JARVIS",
}


def apply_speech_corrections(text: str) -> str:
    """Fix common speech-to-text errors before processing."""
    import re as _stt_re
    result = text
    for pattern, replacement in STT_CORRECTIONS.items():
        result = _stt_re.sub(pattern, replacement, result, flags=_stt_re.IGNORECASE)
    return result


# ---------------------------------------------------------------------------
# LLM Intent Classifier (replaces keyword-based action detection)
# ---------------------------------------------------------------------------

async def classify_intent(text: str) -> dict:
    """Classify every user message using Haiku LLM.

    Returns: {"action": "open_terminal|browse|build|chat", "target": "description"}
    """
    try:
        raw = await _llm_call(
            "Classify this voice command. The user is talking to JARVIS, an AI assistant that can:\n"
            "- Open Terminal and run Claude Code (coding AI tool)\n"
            "- Open Chrome browser for web searches and URLs\n"
            "- Build software projects via Claude Code in Terminal\n"
            "- Research topics by opening Chrome search\n\n"
            "Note: speech-to-text may produce errors like \"Cloud\" for \"Claude\", "
            "\"Travis\" for \"JARVIS\", \"clock code\" for \"Claude Code\".\n\n"
            "Return ONLY valid JSON: {\"action\": \"open_terminal|browse|build|chat\", "
            "\"target\": \"description of what to do\"}\n"
            "open_terminal = user wants to open terminal or launch Claude Code\n"
            "browse = user wants to search the web, look something up, visit a URL\n"
            "build = user wants to create/build a software project\n"
            "chat = just conversation, questions, or anything else\n"
            "If unclear, default to \"chat\".",
            [{"role": "user", "content": text}],
            max_tokens=100,
        )
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        data = json.loads(raw)
        return {
            "action": data.get("action", "chat"),
            "target": data.get("target", text),
        }
    except Exception as e:
        log.warning(f"Intent classification failed: {e}")
        return {"action": "chat", "target": text}


# ---------------------------------------------------------------------------
# Markdown Stripping for TTS
# ---------------------------------------------------------------------------

def strip_markdown_for_tts(text: str) -> str:
    """Strip ALL markdown from text before sending to TTS."""
    import re as _md_re
    result = text
    # Remove code blocks (``` ... ```)
    result = _md_re.sub(r"```[\s\S]*?```", "", result)
    # Remove inline code
    result = result.replace("`", "")
    # Remove bold/italic markers
    result = result.replace("**", "").replace("*", "")
    # Remove headers
    result = _md_re.sub(r"^#{1,6}\s*", "", result, flags=_md_re.MULTILINE)
    # Convert [text](url) to just text
    result = _md_re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", result)
    # Remove bullet points
    result = _md_re.sub(r"^\s*[-*+]\s+", "", result, flags=_md_re.MULTILINE)
    # Remove numbered lists
    result = _md_re.sub(r"^\s*\d+\.\s+", "", result, flags=_md_re.MULTILINE)
    # Double newlines to period
    result = _md_re.sub(r"\n{2,}", ". ", result)
    # Single newlines to space
    result = result.replace("\n", " ")
    # Clean up multiple spaces
    result = _md_re.sub(r"\s{2,}", " ", result)

    # Strip banned phrases
    banned = ["my apologies", "i apologize", "absolutely", "great question",
              "i'd be happy to", "of course", "how can i help",
              "is there anything else", "i should clarify", "let me know if",
              "feel free to"]
    result_lower = result.lower()
    for phrase in banned:
        idx = result_lower.find(phrase)
        while idx != -1:
            # Remove the phrase and any trailing comma/dash
            end = idx + len(phrase)
            if end < len(result) and result[end] in " ,—-":
                end += 1
            result = result[:idx] + result[end:]
            result_lower = result.lower()
            idx = result_lower.find(phrase)

    return result.strip().strip(",").strip("—").strip("-").strip()


# ---------------------------------------------------------------------------
# Action Tag Extraction (parse [ACTION:X] from LLM responses)
# ---------------------------------------------------------------------------

import re as _action_re


def extract_action(response: str) -> tuple[str, dict | None]:
    """Extract [ACTION:X] tag from LLM response.

    Returns (clean_text_for_tts, action_dict_or_none).
    """
    match = _action_re.search(
        r'\[ACTION:(BUILD|BROWSE|RESEARCH|OPEN_TERMINAL|OPEN_APP|PROMPT_PROJECT|ADD_TASK|ADD_NOTE|COMPLETE_TASK|REMEMBER|SCREEN|ASK_VISION)\]\s*(.*?)$',
        response, _action_re.DOTALL,
    )
    if match:
        action_type = match.group(1).lower()
        action_target = match.group(2).strip()
        clean_text = response[:match.start()].strip()
        return clean_text, {"action": action_type, "target": action_target}
    return response, None


async def _execute_build(target: str):
    """Execute a build action from an LLM-embedded [ACTION:BUILD] tag."""
    try:
        await handle_build(target)
    except Exception as e:
        log.error(f"Build execution failed: {e}")


async def _execute_open_app(app_name: str):
    """Execute an open-app action from an LLM-embedded [ACTION:OPEN_APP] tag."""
    try:
        await open_app(app_name)
    except Exception as e:
        log.error(f"Open app execution failed: {e}")


async def _execute_browse(target: str):
    """Execute a browse action from an LLM-embedded [ACTION:BROWSE] tag."""
    try:
        if target.startswith("http") or "." in target.split()[0]:
            await open_browser(target)
        else:
            from urllib.parse import quote
            await open_browser(f"https://www.google.com/search?q={quote(target)}")
    except Exception as e:
        log.error(f"Browse execution failed: {e}")


async def _execute_research(target: str, ws=None):
    """Execute research via claude -p in background. Opens report and speaks when done."""
    try:
        name = _generate_project_name(target)
        path = str(Path.home() / "Desktop" / name)
        os.makedirs(path, exist_ok=True)

        prompt = (
            f"{target}\n\n"
            f"Research this thoroughly. Find REAL data — not made-up examples.\n"
            f"Create a well-designed HTML file called `report.html` in the current directory.\n"
            f"Dark theme, clean typography, organized sections, real links and sources.\n"
            f"The working directory is: {path}"
        )

        log.info(f"Research started via claude -p in {path}")

        cmd = ["claude", "-p", "--output-format", "text"]
        if _SKIP_PERMISSIONS:
            cmd.append("--dangerously-skip-permissions")
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=path,
        )

        stdout, stderr = await asyncio.wait_for(
            process.communicate(input=prompt.encode()),
            timeout=300,
        )

        result = stdout.decode().strip()
        log.info(f"Research complete ({len(result)} chars)")

        recently_built.append({"name": name, "path": path, "time": time.time()})

        # Find and open any HTML report
        report = Path(path) / "report.html"
        if not report.exists():
            # Check for any HTML file
            html_files = list(Path(path).glob("*.html"))
            if html_files:
                report = html_files[0]

        if report.exists():
            await open_browser(f"file://{report}")
            log.info(f"Opened {report.name} in browser")

        # Notify via voice if WebSocket still connected
        if ws:
            try:
                notify_text = f"Research is complete, sir. Report is open in your browser."
                audio = await synthesize_speech(notify_text)
                if audio:
                    await ws.send_json({"type": "status", "state": "speaking"})
                    await ws.send_json({"type": "audio", "data": base64.b64encode(audio).decode(), "text": notify_text})
                    await ws.send_json({"type": "status", "state": "idle"})
                    log.info(f"JARVIS: {notify_text}")
            except Exception:
                pass  # WebSocket might be gone

    except asyncio.TimeoutError:
        log.error("Research timed out after 5 minutes")
        if ws:
            try:
                audio = await synthesize_speech("Research timed out, sir. It was taking too long.")
                if audio:
                    await ws.send_json({"type": "audio", "data": base64.b64encode(audio).decode(), "text": "Research timed out, sir."})
            except Exception:
                pass
    except Exception as e:
        log.error(f"Research execution failed: {e}")


async def _focus_terminal_window(project_name: str):
    """Bring a Terminal/PowerShell window matching the project name to front.
    macOS: AppleScript. Windows: no-op (Windows Terminal doesn't expose this easily).
    """
    if sys.platform == "win32":
        return  # Not supported on Windows
    escaped = applescript_escape(project_name)
    script = f'''
tell application "Terminal"
    repeat with w in windows
        if name of w contains "{escaped}" then
            set index of w to 1
            activate
            exit repeat
        end if
    end repeat
end tell
'''
    try:
        proc = await asyncio.create_subprocess_exec(
            "osascript", "-e", script,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await asyncio.wait_for(proc.communicate(), timeout=5)
    except Exception:
        pass


async def _execute_open_terminal():
    """Execute an open-terminal action from an LLM-embedded [ACTION:OPEN_TERMINAL] tag."""
    try:
        await handle_open_terminal()
    except Exception as e:
        log.error(f"Open terminal failed: {e}")


def _find_project_dir(project_name: str) -> str | None:
    """Find a project directory by name from cached projects or Desktop."""
    for p in cached_projects:
        if project_name.lower() in p.get("name", "").lower():
            return p.get("path")
    desktop = Path.home() / "Desktop"
    for d in desktop.iterdir():
        if d.is_dir() and project_name.lower() in d.name.lower():
            return str(d)
    return None


async def _execute_prompt_project(project_name: str, prompt: str, work_session: WorkSession, ws, dispatch_id: int = None, history: list[dict] = None, voice_state: dict = None):
    """Dispatch a prompt to Claude Code in a project directory.

    Runs entirely in the background. JARVIS returns to conversation mode
    immediately. When Claude Code finishes, JARVIS interrupts to report.
    """
    try:
        project_dir = _find_project_dir(project_name)

        # Register dispatch if not already registered
        if dispatch_id is None:
            dispatch_id = dispatch_registry.register(project_name, project_dir or "", prompt)

        if not project_dir:
            msg = f"Couldn't find the {project_name} project directory, sir."
            audio = await synthesize_speech(msg)
            if audio and ws:
                try:
                    await ws.send_json({"type": "status", "state": "speaking"})
                    await ws.send_json({"type": "audio", "data": base64.b64encode(audio).decode(), "text": msg})
                except Exception:
                    pass
            return

        # Use a SEPARATE session so we don't trap the main conversation
        dispatch = WorkSession()
        await dispatch.start(project_dir, project_name)

        # Bring matching Terminal window to front so user can watch
        asyncio.create_task(_focus_terminal_window(project_name))

        log.info(f"Dispatching to {project_name} in {project_dir}: {prompt[:80]}")
        dispatch_registry.update_status(dispatch_id, "building")

        # Run claude -p in background
        full_response = await dispatch.send(prompt)
        await dispatch.stop()

        # Auto-open any localhost URLs from response
        import re as _re
        # Check for the explicit RUNNING_AT marker first
        running_match = _re.search(r'RUNNING_AT=(https?://localhost:\d+)', full_response or "")
        if not running_match:
            running_match = _re.search(r'https?://localhost:\d+', full_response or "")
        if running_match:
            url = running_match.group(1) if running_match.lastindex else running_match.group(0)
            asyncio.create_task(_execute_browse(url))
            log.info(f"Auto-opening {url}")
            # Store URL in dispatch
            if dispatch_id:
                dispatch_registry.update_status(dispatch_id, "completed",
                    response=full_response[:2000], summary=f"Running at {url}")

        if not full_response or full_response.startswith("Hit a problem") or full_response.startswith("That's taking"):
            dispatch_registry.update_status(dispatch_id, "failed" if full_response else "timeout", response=full_response or "")
            msg = f"Sir, I ran into an issue with {project_name}. {full_response[:150] if full_response else 'No response received.'}"
        else:
            # Summarize via Haiku — don't read word for word
            try:
                msg = await _llm_call(
                    "You are JARVIS reporting back on what you found or built in a project. "
                    "Speak in first person -- 'I found', 'I built', 'I reviewed'. "
                    "Start with 'Sir, ' to get the user's attention. "
                    "Be specific but concise -- highlight the key findings or actions taken. "
                    "If there are multiple items, give the count and top 2-3 briefly. "
                    "End by asking how the user wants to proceed. "
                    "NEVER read out URLs or localhost addresses. NEVER say 'Claude Code'. "
                    "2-3 sentences max. No markdown. Natural spoken voice.",
                    [{"role": "user", "content": f"Project: {project_name}\nClaude Code reported:\n{full_response[:3000]}"}],
                    max_tokens=150,
                )
            except Exception:
                msg = f"Sir, {project_name} finished. Here's the gist: {full_response[:200]}"

        # Speak the result — skip if user has spoken recently to avoid audio collision
        log.info(f"Dispatch summary for {project_name}: {msg[:100]}")
        if voice_state and time.time() - voice_state["last_user_time"] < 3:
            log.info(f"Skipping dispatch audio for {project_name} — user spoke recently")
            # Result is still stored in history below so JARVIS can reference it
        else:
            audio = await synthesize_speech(strip_markdown_for_tts(msg))
            if ws:
                try:
                    await ws.send_json({"type": "status", "state": "speaking"})
                    if audio:
                        await ws.send_json({"type": "audio", "data": base64.b64encode(audio).decode(), "text": msg})
                        log.info(f"Dispatch audio sent for {project_name}")
                    else:
                        await ws.send_json({"type": "text", "text": msg})
                        log.info(f"Dispatch text fallback sent for {project_name}")
                except Exception as e:
                    log.error(f"Dispatch audio send failed: {e}")

        # Store dispatch result in conversation history so JARVIS remembers it
        if history is not None:
            history.append({"role": "assistant", "content": f"[Dispatch result for {project_name}]: {msg}"})

        dispatch_registry.update_status(dispatch_id, "completed", response=full_response[:2000], summary=msg[:200])
        log.info(f"Project {project_name} dispatch complete ({len(full_response)} chars)")

    except Exception as e:
        log.error(f"Prompt project failed: {e}", exc_info=True)
        try:
            msg = f"Had trouble connecting to {project_name}, sir."
            audio = await synthesize_speech(msg)
            if audio and ws:
                await ws.send_json({"type": "status", "state": "speaking"})
                await ws.send_json({"type": "audio", "data": base64.b64encode(audio).decode(), "text": msg})
        except Exception:
            pass


async def self_work_and_notify(session: WorkSession, prompt: str, ws):
    """Run claude -p in background and notify via voice when done."""
    try:
        full_response = await session.send(prompt)
        log.info(f"Background work complete ({len(full_response)} chars)")

        # Summarize and speak
        if full_response:
            try:
                msg = await _llm_call(
                    "You are JARVIS. Summarize what you just completed in 1 sentence. First person -- 'I built', 'I set up'. No markdown. Never say 'Claude Code'.",
                    [{"role": "user", "content": f"Claude Code completed:\n{full_response[:2000]}"}],
                    max_tokens=100,
                )
            except Exception:
                msg = "Work is complete, sir."

            try:
                audio = await synthesize_speech(msg)
                if audio:
                    await ws.send_json({"type": "status", "state": "speaking"})
                    await ws.send_json({"type": "audio", "data": base64.b64encode(audio).decode(), "text": msg})
                    await ws.send_json({"type": "status", "state": "idle"})
                    log.info(f"JARVIS: {msg}")
            except Exception:
                pass
    except Exception as e:
        log.error(f"Background work failed: {e}")



# ---------------------------------------------------------------------------
# TTS (Edge TTS)
# ---------------------------------------------------------------------------

async def synthesize_speech(text: str, voice: Optional[str] = None) -> Optional[bytes]:
    """Generate speech using Microsoft Edge TTS.

    voice overrides the default EDGE_TTS_VOICE — used for multilingual responses.
    """
    try:
        import edge_tts
        import io
        selected_voice = voice or EDGE_TTS_VOICE
        communicate = edge_tts.Communicate(text, selected_voice)
        buf = io.BytesIO()
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                buf.write(chunk["data"])
        audio = buf.getvalue()
        if audio:
            _session_tokens["tts_calls"] += 1
            _append_usage_entry(0, 0, "tts")
            log.info(f"Edge TTS ({selected_voice}): {len(audio)} bytes")
            return audio
    except Exception as e:
        log.error(f"Edge TTS failed: {e}")
    return None


# ---------------------------------------------------------------------------
# LLM Response
# ---------------------------------------------------------------------------


async def _call_openai_compat(
    base_url: str, model: str, api_key: str,
    messages: list[dict], max_tokens: int,
    connect_timeout: float = 5.0, read_timeout: float = 30.0,
) -> str:
    """Call any OpenAI-compatible chat completions endpoint."""
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    url = f"{base_url.rstrip('/')}/v1/chat/completions"
    payload = {"model": model, "messages": messages, "max_tokens": max_tokens, "stream": False}
    async with httpx.AsyncClient(timeout=httpx.Timeout(connect_timeout, read=read_timeout)) as http:
        resp = await http.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()


async def _llm_call(system: str, messages: list[dict], max_tokens: int = 250) -> str:
    """Call Groq with retry on rate-limit; fall back to local Ollama only if reachable."""
    chat_msgs: list[dict] = []
    if system:
        chat_msgs.append({"role": "system", "content": system})
    for m in messages:
        role = m.get("role", "user")
        content = m.get("content", "")
        if isinstance(content, list):
            content = " ".join(b.get("text", "") for b in content if isinstance(b, dict))
        chat_msgs.append({"role": role, "content": content})

    # Primary LLM (Groq when configured) — single attempt, fail fast on rate limits
    if OLLAMA_BASE_URL and OLLAMA_BASE_URL.rstrip('/') != LOCAL_OLLAMA_URL.rstrip('/'):
        try:
            return await _call_openai_compat(
                OLLAMA_BASE_URL, OLLAMA_MODEL, OLLAMA_API_KEY,
                chat_msgs, max_tokens,
                connect_timeout=5.0, read_timeout=30.0,
            )
        except httpx.HTTPStatusError as e:
            status = e.response.status_code
            if status == 429:
                # Respect Retry-After header — but only wait if it's short (≤ 4s)
                retry_after = e.response.headers.get("retry-after", "")
                try:
                    wait_s = float(retry_after)
                except (ValueError, TypeError):
                    wait_s = 99.0  # Unknown — don't wait
                if 0 < wait_s <= 4.0:
                    log.warning(f"Primary LLM 429, waiting {wait_s}s (Retry-After header)")
                    await asyncio.sleep(wait_s)
                    try:
                        return await _call_openai_compat(
                            OLLAMA_BASE_URL, OLLAMA_MODEL, OLLAMA_API_KEY,
                            chat_msgs, max_tokens,
                            connect_timeout=5.0, read_timeout=30.0,
                        )
                    except Exception as e2:
                        log.warning(f"Primary LLM retry failed: {e2}")
                else:
                    log.warning(f"Primary LLM rate limited (429) — failing fast, no retry")
            elif 500 <= status < 600:
                log.warning(f"Primary LLM {status} server error — failing fast")
            else:
                log.warning(f"Primary LLM HTTP {status}: {e}")
        except Exception as e:
            log.warning(f"Primary LLM error: {e}")

    # Local Ollama fallback — only if explicitly enabled AND different from primary
    _local_enabled = os.getenv("LOCAL_OLLAMA", "false").lower() in ("true", "1", "yes")
    if _local_enabled and LOCAL_OLLAMA_URL.rstrip('/') != OLLAMA_BASE_URL.rstrip('/'):
        try:
            return await _call_openai_compat(
                LOCAL_OLLAMA_URL, LOCAL_OLLAMA_MODEL, "",
                chat_msgs, max_tokens,
                connect_timeout=1.5, read_timeout=10.0,
            )
        except Exception as e:
            log.debug(f"Local Ollama unavailable: {e}")

    return "Apologies, sir. I'm rate limited — try again in a moment."


async def generate_response(
    text: str,
    task_mgr: ClaudeTaskManager,
    projects: list[dict],
    conversation_history: list[dict],
    last_response: str = "",
    session_summary: str = "",
) -> str:
    """Generate a JARVIS response."""
    now = datetime.now()

    # Use cached context (refreshed in background, never blocks responses)
    screen_ctx = _ctx_cache["screen"]

    # Check if any lookups are in progress
    lookup_status = get_lookup_status()

    system = JARVIS_SYSTEM_PROMPT.format(
        screen_context=screen_ctx or "Not checked yet.",
        active_tasks=task_mgr.get_active_tasks_summary(),
        dispatch_context=dispatch_registry.format_for_prompt(),
        known_projects=format_projects_for_prompt(projects),
        user_name=USER_NAME,
        project_dir=PROJECT_DIR,
    )

    # Only inject time/weather if user asks about them (check for keywords)
    if any(keyword in text.lower() for keyword in ["time", "what's the time", "what time", "weather", "temperature", "forecast"]):
        current_time = now.strftime("%A, %B %d, %Y at %I:%M %p")
        weather_info = _ctx_cache.get("weather", "Weather data unavailable.")
        system += f"\n\nCURRENT TIME: {current_time}\nWEATHER: {weather_info}"
    if lookup_status:
        system += f"\n\nACTIVE LOOKUPS:\n{lookup_status}\nIf asked about progress, report this status."

    # Inject relevant memories and tasks (run in thread to avoid blocking event loop)
    loop = asyncio.get_event_loop()
    memory_ctx = await loop.run_in_executor(None, build_memory_context, text)
    if memory_ctx:
        system += f"\n\nJARVIS MEMORY:\n{memory_ctx}"

    # Three-tier memory — inject rolling summary of earlier conversation
    if session_summary:
        system += f"\n\nSESSION CONTEXT (earlier in this conversation):\n{session_summary}"

    # Self-awareness — remind JARVIS of last response to avoid repetition
    if last_response:
        system += f'\n\nYOUR LAST RESPONSE (do not repeat this):\n"{last_response[:150]}"'

    # Use conversation history — keep the last 20 messages for context
    # (older conversation is captured in session_summary)
    messages = conversation_history[-20:]
    # If the last message isn't the current user text, add it
    if not messages or messages[-1].get("content") != text:
        messages = messages + [{"role": "user", "content": text}]

    try:
        return await _llm_call(system, messages, max_tokens=250)
    except Exception as e:
        log.error(f"LLM error: {e}")
        return "Apologies, sir. I'm having trouble connecting to my language systems."


# ---------------------------------------------------------------------------
# FastAPI App
# ---------------------------------------------------------------------------

# Shared state
task_manager = ClaudeTaskManager(max_concurrent=3)
cached_projects: list[dict] = []
recently_built: list[dict] = []  # [{"name": str, "path": str, "time": float}]
dispatch_registry = DispatchRegistry()

# VISION — knowledge agent (Wikipedia + persistent learning)
_VISION_DB   = Path(__file__).parent / "data" / "vision_knowledge.db"
vision_agent = VisionAgent(str(_VISION_DB))

# Usage tracking — logs every call with timestamp, persists to disk
_USAGE_FILE = Path(__file__).parent / "data" / "usage_log.jsonl"
_session_start = time.time()
_server_start_time = _session_start
_session_tokens = {"input": 0, "output": 0, "api_calls": 0, "tts_calls": 0}


def _append_usage_entry(input_tokens: int, output_tokens: int, call_type: str = "api"):
    """Append a usage entry with timestamp to the log file."""
    try:
        _USAGE_FILE.parent.mkdir(parents=True, exist_ok=True)
        import json as _json
        entry = {
            "ts": time.time(),
            "date": datetime.now().strftime("%Y-%m-%d"),
            "type": call_type,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
        }
        with open(_USAGE_FILE, "a") as f:
            f.write(_json.dumps(entry) + "\n")
    except Exception:
        pass


def _get_usage_for_period(seconds: float | None = None) -> dict:
    """Sum usage from the log file for a time period. None = all time."""
    import json as _json
    totals = {"input_tokens": 0, "output_tokens": 0, "api_calls": 0, "tts_calls": 0}
    cutoff = (time.time() - seconds) if seconds else 0
    try:
        if _USAGE_FILE.exists():
            for line in _USAGE_FILE.read_text().strip().split("\n"):
                if not line:
                    continue
                entry = _json.loads(line)
                if entry["ts"] >= cutoff:
                    totals["input_tokens"] += entry.get("input_tokens", 0)
                    totals["output_tokens"] += entry.get("output_tokens", 0)
                    if entry.get("type") == "tts":
                        totals["tts_calls"] += 1
                    else:
                        totals["api_calls"] += 1
    except Exception:
        pass
    return totals


def _cost_from_tokens(input_t: int, output_t: int) -> float:
    return (input_t / 1_000_000) * 0.80 + (output_t / 1_000_000) * 4.00


def track_usage(response):
    """Track token usage from an Anthropic API response."""
    inp = getattr(response.usage, "input_tokens", 0) if hasattr(response, "usage") else 0
    out = getattr(response.usage, "output_tokens", 0) if hasattr(response, "usage") else 0
    _session_tokens["input"] += inp
    _session_tokens["output"] += out
    _session_tokens["api_calls"] += 1
    _append_usage_entry(inp, out, "api")


def get_usage_summary() -> str:
    """Get a voice-friendly usage summary with time breakdowns."""
    uptime_min = int((time.time() - _session_start) / 60)

    session = _session_tokens
    today = _get_usage_for_period(86400)
    week = _get_usage_for_period(86400 * 7)
    all_time = _get_usage_for_period(None)

    session_cost = _cost_from_tokens(session["input"], session["output"])
    today_cost = _cost_from_tokens(today["input_tokens"], today["output_tokens"])
    all_cost = _cost_from_tokens(all_time["input_tokens"], all_time["output_tokens"])

    parts = [f"This session: {uptime_min} minutes, {session['api_calls']} calls, ${session_cost:.2f}."]

    if today["api_calls"] > session["api_calls"]:
        parts.append(f"Today total: {today['api_calls']} calls, ${today_cost:.2f}.")

    if all_time["api_calls"] > today["api_calls"]:
        parts.append(f"All time: {all_time['api_calls']} calls, ${all_cost:.2f}.")

    return " ".join(parts)

# Background context cache — never blocks responses
_ctx_cache = {
    "screen": "",
    "weather": "Weather data unavailable.",
}


def _refresh_context_sync():
    """Run in a SEPARATE THREAD — refreshes screen/weather context.

    Uses PowerShell on Windows to list open windows.
    Runs off the async event loop so it never blocks responses.
    """
    import subprocess, threading

    def _get_windows_screen():
        """Windows: PowerShell to list processes with visible window titles."""
        ps_cmd = (
            "Get-Process | Where-Object {$_.MainWindowTitle -ne ''} | "
            "Select-Object ProcessName, MainWindowTitle | "
            "ForEach-Object { $_.ProcessName + '|||' + $_.MainWindowTitle }"
        )
        try:
            proc = subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps_cmd],
                capture_output=True, text=True, timeout=8
            )
            windows = []
            first = True
            for line in proc.stdout.strip().split("\n"):
                parts = line.strip().split("|||")
                if len(parts) >= 2 and parts[0].strip():
                    windows.append({
                        "app": parts[0].strip(),
                        "title": parts[1].strip(),
                        "frontmost": first,
                    })
                    first = False
            return windows
        except Exception:
            return []

    def _worker():
        while True:
            try:
                windows = _get_windows_screen()
                if windows:
                    _ctx_cache["screen"] = format_windows_for_context(windows)
            except Exception as e:
                log.debug(f"Screen refresh error: {e}")

            # Weather refresh
            try:
                weather_string = _fetch_weather_string_sync()
                if weather_string:
                    _ctx_cache["weather"] = weather_string
            except Exception as e:
                log.debug(f"Weather refresh error: {e}")

            time.sleep(30)

    t = threading.Thread(target=_worker, daemon=True)
    t.start()
    log.info("Context refresh thread started")


@asynccontextmanager
async def lifespan(application: FastAPI):
    global cached_projects

    # Start context refresh in a separate thread (never touches event loop)
    _refresh_context_sync()
    log.info("JARVIS server starting")

    yield


app = FastAPI(title="JARVIS Server", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# -- REST Endpoints --------------------------------------------------------

@app.get("/api/health")
async def health():
    return {"status": "online", "name": "JARVIS", "version": "0.1.0"}


@app.get("/api/tts-test")
async def tts_test():
    """Generate a test audio clip for debugging."""
    audio = await synthesize_speech("Testing audio, sir.")
    if audio:
        return {"audio": base64.b64encode(audio).decode()}
    return {"audio": None, "error": "TTS failed"}


@app.get("/api/usage")
async def api_usage():
    uptime = int(time.time() - _session_start)
    today = _get_usage_for_period(86400)
    week = _get_usage_for_period(86400 * 7)
    month = _get_usage_for_period(86400 * 30)
    all_time = _get_usage_for_period(None)
    return {
        "session": {**_session_tokens, "uptime_seconds": uptime},
        "today": {**today, "cost_usd": round(_cost_from_tokens(today["input_tokens"], today["output_tokens"]), 4)},
        "week": {**week, "cost_usd": round(_cost_from_tokens(week["input_tokens"], week["output_tokens"]), 4)},
        "month": {**month, "cost_usd": round(_cost_from_tokens(month["input_tokens"], month["output_tokens"]), 4)},
        "all_time": {**all_time, "cost_usd": round(_cost_from_tokens(all_time["input_tokens"], all_time["output_tokens"]), 4)},
    }


@app.get("/api/tasks")
async def api_list_tasks():
    tasks = await task_manager.list_tasks()
    return {"tasks": [t.to_dict() for t in tasks]}


@app.get("/api/tasks/{task_id}")
async def api_get_task(task_id: str):
    task = await task_manager.get_status(task_id)
    if not task:
        return JSONResponse(status_code=404, content={"error": "Task not found"})
    return {"task": task.to_dict()}


@app.post("/api/tasks")
async def api_create_task(req: TaskRequest):
    try:
        task_id = await task_manager.spawn(req.prompt, req.working_dir)
        return {"task_id": task_id, "status": "spawned"}
    except RuntimeError as e:
        return JSONResponse(status_code=429, content={"error": str(e)})


@app.delete("/api/tasks/{task_id}")
async def api_cancel_task(task_id: str):
    cancelled = await task_manager.cancel(task_id)
    if not cancelled:
        return JSONResponse(
            status_code=404,
            content={"error": "Task not found or not cancellable"},
        )
    return {"task_id": task_id, "status": "cancelled"}


@app.get("/api/projects")
async def api_list_projects():
    global cached_projects
    cached_projects = await scan_projects()
    return {"projects": cached_projects}


# -- Fast Action Detection (no LLM call) -----------------------------------

def _scan_projects_sync() -> list[dict]:
    """Synchronous Desktop scan — runs in executor."""
    projects = []
    desktop = Path.home() / "Desktop"
    try:
        for entry in desktop.iterdir():
            if entry.is_dir() and not entry.name.startswith("."):
                projects.append({"name": entry.name, "path": str(entry), "branch": ""})
    except Exception:
        pass
    return projects


def detect_dismissal_or_casual(text: str) -> str | None:
    """Detect casual remarks that don't need full LLM processing.

    Returns a dismissal response if detected, None otherwise.
    """
    t = text.lower().strip()

    # Dismissal/cancellation phrases — respond immediately without action
    dismissals = {
        "leave it": "Right then, sir.",
        "nevermind": "Understood, sir.",
        "never mind": "Understood, sir.",
        "scratch that": "Cancelled, sir.",
        "forget it": "Consider it forgotten, sir.",
        "don't bother": "Say no more, sir.",
        "nah": "Very good, sir.",
        "nope": "Understood, sir.",
        "no": "Right then, sir.",
        "forget i said anything": "As if it never happened, sir.",
        "forget that": "Forgotten, sir.",
        "scratch it": "Consider it cancelled, sir.",
    }

    for phrase, response in dismissals.items():
        if t == phrase or t.startswith(phrase + " ") or t.startswith(phrase + "."):
            return response

    # Very short acknowledgments — don't search or execute for these
    if t in ["ok", "okay", "cool", "alright", "right", "yes", "yeah", "yep", "fine", "good"]:
        return "Understood, sir."

    return None


def detect_action_fast(text: str) -> dict | None:
    """Keyword-based action detection — ONLY for short, obvious commands.

    Everything else goes to the LLM which uses [ACTION:X] tags when it decides
    to act based on conversational understanding.
    """
    t = text.lower().strip()
    words = t.split()

    # Only trigger on SHORT, clear commands (< 12 words)
    if len(words) > 12:
        return None  # Long messages are conversation, not commands

    # Screen requests — checked BEFORE project matching to prevent misrouting
    if any(p in t for p in ["look at my screen", "what's on my screen", "whats on my screen",
                             "what am i looking at", "what do you see", "see my screen",
                             "what's running on my", "whats running on my", "check my screen"]):
        return {"action": "describe_screen"}

    # Terminal / Claude Code — explicit open requests
    if any(w in t for w in ["open claude", "start claude", "launch claude", "run claude"]):
        return {"action": "open_terminal"}

    # Show recent build
    if any(w in t for w in ["show me what you built", "pull up what you made", "open what you built"]):
        return {"action": "show_recent"}

    # Screen awareness — explicit look/see requests
    if any(p in t for p in ["what's on my screen", "whats on my screen", "what do you see",
                             "can you see my screen", "look at my screen", "what am i looking at",
                             "what's open", "whats open", "what apps are open"]):
        return {"action": "describe_screen"}

    # Open Windows apps — "open notepad", "launch spotify", "start discord"
    open_app_words = ["open ", "launch ", "start ", "run "]
    if any(t.startswith(w) or f" {w}" in t for w in open_app_words):
        # Extract the app name after the verb
        for w in open_app_words:
            idx = t.find(w)
            if idx != -1:
                app_candidate = t[idx + len(w):].strip().rstrip(".")
                # Exclude things that should go to other handlers
                skip_terms = ["terminal", "claude", "chrome", "browser", "firefox", "build", "project"]
                if app_candidate and not any(s in app_candidate for s in skip_terms) and len(app_candidate) > 1:
                    return {"action": "open_app", "target": app_candidate}
                break

    # Dispatch / build status check
    if any(p in t for p in ["where are we", "where were we", "project status", "how's the build",
                             "hows the build", "status update", "status report", "where is that",
                             "how's it going with", "hows it going with", "is it done",
                             "is that done", "what happened with"]):
        return {"action": "check_dispatch"}

    # Task list check
    if any(p in t for p in ["what's on my list", "whats on my list", "my tasks", "my to do",
                             "my todo", "what do i need to do", "open tasks", "task list"]):
        return {"action": "check_tasks"}

    # Usage / cost check
    if any(p in t for p in ["usage", "how much have you cost", "how much am i spending",
                             "what's the cost", "whats the cost", "api cost", "token usage",
                             "how expensive", "what's my bill"]):
        return {"action": "check_usage"}

    # VISION feedback shortcuts
    if any(p in t for p in ["vision was wrong", "vision got it wrong", "vision is wrong",
                             "that's wrong", "thats wrong", "incorrect", "vision made a mistake"]):
        return {"action": "vision_feedback", "correct": False}
    if any(p in t for p in ["vision was right", "vision got it right", "vision is right",
                             "that's correct", "thats correct", "vision was correct"]):
        return {"action": "vision_feedback", "correct": True}

    return None  # Everything else goes to the LLM for conversational routing


# -- Action Handlers -------------------------------------------------------

async def handle_open_terminal() -> str:
    claude_cmd = "claude --dangerously-skip-permissions" if _SKIP_PERMISSIONS else "claude"
    result = await open_terminal(claude_cmd)
    return result["confirmation"]


async def handle_build(target: str) -> str:
    name = _generate_project_name(target)
    path = str(Path.home() / "Desktop" / name)
    os.makedirs(path, exist_ok=True)

    # Write CLAUDE.md with clear instructions
    claude_md = Path(path) / "CLAUDE.md"
    claude_md.write_text(f"# Task\n\n{target}\n\nBuild this completely. If web app, make index.html work standalone.\n")

    result = await open_claude_in_project(path, target)
    recently_built.append({"name": name, "path": path, "time": time.time()})
    return f"On it, sir. Claude Code is working in {name}."


async def handle_show_recent() -> str:
    if not recently_built:
        return "Nothing built recently, sir."
    last = recently_built[-1]
    project_path = Path(last["path"])

    # Try to find the best file to open
    for name in ["report.html", "index.html"]:
        f = project_path / name
        if f.exists():
            await open_browser(f"file://{f}")
            return f"Opened {name} from {last['name']}, sir."

    # Try any HTML file
    html_files = list(project_path.glob("*.html"))
    if html_files:
        await open_browser(f"file://{html_files[0]}")
        return f"Opened {html_files[0].name} from {last['name']}, sir."

    # Fall back to opening the folder in File Explorer (Windows) or Finder (macOS)
    folder_path = last["path"]
    if sys.platform == "win32":
        await asyncio.create_subprocess_exec(
            "explorer", folder_path,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        return f"Opened the {last['name']} folder in File Explorer, sir."
    else:
        escaped_last_path = applescript_escape(folder_path)
        script = f'tell application "Finder"\nactivate\nopen POSIX file "{escaped_last_path}"\nend tell'
        await asyncio.create_subprocess_exec("osascript", "-e", script, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        return f"Opened the {last['name']} folder in Finder, sir."


# ---------------------------------------------------------------------------
# Background lookup system — spawns slow tasks, reports back via voice
# ---------------------------------------------------------------------------

# Track active lookups so JARVIS can report status
_active_lookups: dict[str, dict] = {}  # id -> {"type": str, "status": str, "started": float}


async def _lookup_and_report(lookup_type: str, lookup_fn, ws, history: list[dict] = None, voice_state: dict = None):
    """Run a slow lookup, then speak the result back.

    JARVIS stays conversational — this runs completely off the main path.
    """
    lookup_id = str(uuid.uuid4())[:8]
    _active_lookups[lookup_id] = {
        "type": lookup_type,
        "status": "working",
        "started": time.time(),
    }

    try:
        # Run the async lookup directly — these functions already use
        # asyncio.create_subprocess_exec so they don't block the event loop
        result_text = await asyncio.wait_for(
            lookup_fn(),
            timeout=30,
        )

        _active_lookups[lookup_id]["status"] = "done"

        # Speak the result — skip audio if user spoke recently to avoid collision
        if voice_state and time.time() - voice_state["last_user_time"] < 3:
            log.info(f"Skipping lookup audio for {lookup_type} — user spoke recently")
            # Result is still stored in history below
        else:
            tts = strip_markdown_for_tts(result_text)
            audio = await synthesize_speech(tts)
            try:
                await ws.send_json({"type": "status", "state": "speaking"})
                if audio:
                    await ws.send_json({"type": "audio", "data": audio, "text": result_text})
                else:
                    await ws.send_json({"type": "text", "text": result_text})
                await ws.send_json({"type": "status", "state": "idle"})
            except Exception:
                pass

        log.info(f"Lookup {lookup_type} complete: {result_text[:80]}")

        # Store lookup result in conversation history so JARVIS remembers it
        if history is not None:
            history.append({"role": "assistant", "content": f"[{lookup_type} check]: {result_text}"})

    except asyncio.TimeoutError:
        _active_lookups[lookup_id]["status"] = "timeout"
        try:
            fallback = f"That {lookup_type} check is taking too long, sir. The data may still be syncing."
            audio = await synthesize_speech(fallback)
            await ws.send_json({"type": "status", "state": "speaking"})
            if audio:
                await ws.send_json({"type": "audio", "data": audio, "text": fallback})
            await ws.send_json({"type": "status", "state": "idle"})
        except Exception:
            pass
    except Exception as e:
        _active_lookups[lookup_id]["status"] = "error"
        log.warning(f"Lookup {lookup_type} failed: {e}")
    finally:
        # Clean up after 60s
        await asyncio.sleep(60)
        _active_lookups.pop(lookup_id, None)



async def _do_screen_lookup() -> str:
    """Screen describe — runs in thread."""
    return await describe_screen()
    windows = await get_active_windows()
    if windows:
        apps = set(w["app"] for w in windows)
        active = next((w for w in windows if w["frontmost"]), None)
        result = f"You have {', '.join(apps)} open."
        if active:
            result += f" Currently focused on {active['app']}: {active['title']}."
        return result
    return "Couldn't see the screen, sir."


def get_lookup_status() -> str:
    """Get status of active lookups for when user asks 'how's that coming'."""
    if not _active_lookups:
        return ""
    active = [v for v in _active_lookups.values() if v["status"] == "working"]
    if not active:
        return ""
    parts = []
    for lookup in active:
        elapsed = int(time.time() - lookup["started"])
        parts.append(f"{lookup['type']} check ({elapsed}s)")
    return "Currently working on: " + ", ".join(parts)


def _short_sender(sender: str) -> str:
    """Extract just the name from an email sender string."""
    if "<" in sender:
        return sender.split("<")[0].strip().strip('"')
    if "@" in sender:
        return sender.split("@")[0]
    return sender


async def handle_browse(text: str, target: str) -> str:
    """Open a URL directly or search. Smart about detecting URLs in speech."""
    import re
    from urllib.parse import quote

    browser = "firefox" if "firefox" in text.lower() else "chrome"
    combined = text.lower()

    # 1. Try to find a URL or domain in the text
    # Match things like "joetmd.com", "google.com/maps", "https://example.com"
    url_pattern = r'(?:https?://)?(?:www\.)?([a-zA-Z0-9][-a-zA-Z0-9]*(?:\.[a-zA-Z]{2,})+(?:/[^\s]*)?)'
    url_match = re.search(url_pattern, text, re.IGNORECASE)

    if url_match:
        domain = url_match.group(0)
        if not domain.startswith("http"):
            domain = "https://" + domain
        await open_browser(domain, browser)
        return f"Opened {url_match.group(0)}, sir."

    # 2. Check for spoken domains that speech-to-text mangled
    # "Joe tmd.com" → "joetmd.com", "roofo.co" etc.
    # Try joining words that end/start with a dot pattern
    words = text.split()
    for i, word in enumerate(words):
        # Look for word ending with common TLD
        if re.search(r'\.(com|co|io|ai|org|net|dev|app)$', word, re.IGNORECASE):
            # This word IS a domain — might have spaces before it
            domain = word
            # Check if previous word should be joined (e.g., "Joe tmd.com" → "joetmd.com" is tricky)
            if not domain.startswith("http"):
                domain = "https://" + domain
            await open_browser(domain, browser)
            return f"Opened {word}, sir."

    # 3. Fall back to Google search with cleaned query
    query = target
    for prefix in ["search for", "look up", "google", "find me", "pull up", "open chrome",
                    "open firefox", "open browser", "go to", "can you", "in the browser",
                    "can you go to", "please"]:
        query = query.lower().replace(prefix, "").strip()
    # Remove filler words
    query = re.sub(r'\b(can|you|the|in|to|a|an|for|me|my|please)\b', '', query).strip()
    query = re.sub(r'\s+', ' ', query).strip()

    if not query:
        query = target

    url = f"https://www.google.com/search?q={quote(query)}"
    await open_browser(url, browser)
    return "Searching for that, sir."


async def handle_research(text: str, target: str) -> str:
    """Deep research with Opus — write results to HTML, open in browser."""
    try:
        research_text = await _llm_call(
            f"You are JARVIS, researching a topic for {USER_NAME}. Be thorough, organized, and cite sources where possible.",
            [{"role": "user", "content": f"Research this thoroughly:\n\n{target}"}],
            max_tokens=2000,
        )

        import html as _html
        html_content = f"""<!DOCTYPE html>
<html><head>
<meta charset="utf-8">
<title>JARVIS Research: {_html.escape(target[:60])}</title>
<style>
body {{ font-family: -apple-system, system-ui, sans-serif; max-width: 800px; margin: 40px auto; padding: 20px; background: #0a0a0a; color: #e0e0e0; line-height: 1.7; }}
h1 {{ color: #0ea5e9; font-size: 1.4em; border-bottom: 1px solid #222; padding-bottom: 10px; }}
h2 {{ color: #38bdf8; font-size: 1.1em; margin-top: 24px; }}
a {{ color: #0ea5e9; }}
pre {{ background: #111; padding: 12px; border-radius: 6px; overflow-x: auto; }}
code {{ background: #111; padding: 2px 6px; border-radius: 3px; font-size: 0.9em; }}
blockquote {{ border-left: 3px solid #0ea5e9; margin-left: 0; padding-left: 16px; color: #aaa; }}
</style>
</head><body>
<h1>Research: {_html.escape(target[:80])}</h1>
<div>{research_text.replace(chr(10), '<br>')}</div>
<hr style="border-color:#222;margin-top:40px">
<p style="color:#555;font-size:0.8em">Researched by JARVIS using Claude Opus &bull; {datetime.now().strftime('%B %d, %Y %I:%M %p')}</p>
</body></html>"""

        results_file = Path.home() / "Desktop" / ".jarvis_research.html"
        results_file.write_text(html_content)

        browser_name = "firefox" if "firefox" in text.lower() else "chrome"
        await open_browser(f"file://{results_file}", browser_name)

        voice_summary = await _llm_call(
            "Summarize this research in ONE sentence for voice. No markdown.",
            [{"role": "user", "content": research_text[:2000]}],
            max_tokens=80,
        )
        return voice_summary + " Full results are in your browser, sir."

    except Exception as e:
        log.error(f"Research failed: {e}")
        from urllib.parse import quote
        await open_browser(f"https://www.google.com/search?q={quote(target)}")
        return "Pulled up a search for that, sir."


# -- Session Summary (Three-Tier Memory) -----------------------------------

async def _update_session_summary(
    old_summary: str,
    rotated_messages: list[dict],
) -> str:
    """Background Haiku call to update the rolling session summary."""
    prompt = f"""Update this conversation summary to include the new messages.

Current summary: {old_summary or '(start of conversation)'}

New messages to incorporate:
{chr(10).join(f'{m["role"]}: {m["content"][:200]}' for m in rotated_messages)}

Write an updated summary in 2-4 sentences capturing the key topics, decisions, and context. Be concise."""

    try:
        return (await _llm_call("", [{"role": "user", "content": prompt}], max_tokens=200)).strip()
    except Exception as e:
        log.warning(f"Summary update failed: {e}")
        return old_summary


# -- WebSocket Voice Handler -----------------------------------------------

@app.websocket("/ws/voice")
async def voice_handler(ws: WebSocket):
    """
    WebSocket protocol:

    Client -> Server:
        {"type": "transcript", "text": "...", "isFinal": true}

    Server -> Client:
        {"type": "audio", "data": "<base64 mp3>", "text": "spoken text"}
        {"type": "status", "state": "thinking"|"speaking"|"idle"|"working"}
        {"type": "task_spawned", "task_id": "...", "prompt": "..."}
        {"type": "task_complete", "task_id": "...", "summary": "..."}
    """
    await ws.accept()
    task_manager.register_websocket(ws)
    history: list[dict] = []
    work_session = WorkSession()
    planner = TaskPlanner()

    # Response cancellation — when new input arrives, cancel current response
    _current_response_id = 0
    _cancel_response = False

    # Audio collision prevention — track when user last spoke
    voice_state = {"last_user_time": 0.0}

    # Self-awareness — track last spoken response to avoid repetition
    last_jarvis_response = ""

    # Three-tier conversation memory
    session_buffer: list[dict] = []  # ALL messages, never truncated
    session_summary: str = ""  # Rolling summary of older conversation
    summary_update_pending: bool = False

    # Multilingual session state — persists across turns
    _session_lang: Optional[str] = None  # ISO 639-1 code if non-English, else None
    messages_since_last_summary: int = 0

    log.info("Voice WebSocket connected")

    try:
        try:
            await ws.send_json({"type": "status", "state": "idle"})
        except Exception:
            return  # WebSocket already gone

        while True:
            raw = await ws.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue

            # ── Fix-self: activate work mode in JARVIS repo ──
            if msg.get("type") == "fix_self":
                jarvis_dir = str(Path(__file__).parent)
                await work_session.start(jarvis_dir)
                response_text = "Work mode active in my own repo, sir. Tell me what needs fixing."
                tts = strip_markdown_for_tts(response_text)
                await ws.send_json({"type": "status", "state": "speaking"})
                audio = await synthesize_speech(tts)
                if audio:
                    await ws.send_json({"type": "audio", "data": audio, "text": response_text})
                else:
                    await ws.send_json({"type": "text", "text": response_text})
                continue

            if msg.get("type") != "transcript" or not msg.get("isFinal"):
                continue

            user_text = apply_speech_corrections(msg.get("text", "").strip())
            if not user_text:
                continue

            # Multilingual detection
            # 1. Trust lang hint from frontend (Web Speech API recognition.lang)
            frontend_lang = msg.get("lang", "")  # e.g. "hi-IN", "sv-SE"
            if frontend_lang:
                base_lang = frontend_lang.split("-")[0].lower()
                if is_supported(base_lang):
                    _session_lang = base_lang
                elif base_lang == "en":
                    _session_lang = None

            # 2. Fallback: detect from text content
            if _session_lang is None and frontend_lang.startswith("en"):
                pass  # trust English hint, skip detection
            elif _session_lang is None:
                detected_lang = detect_language(user_text)
                if is_supported(detected_lang):
                    _session_lang = detected_lang
                elif detected_lang and detected_lang.startswith("en"):
                    _session_lang = None

            # Translate non-English input to English for LLM + VISION processing
            if _session_lang:
                user_text_native = user_text
                user_text = translate(user_text, _session_lang, "en")
                log.info(f"Multilingual [{get_language_name(_session_lang)}]: {user_text_native!r} → {user_text!r}")
            else:
                user_text_native = user_text

            # Cancel any in-flight response
            _current_response_id += 1
            my_response_id = _current_response_id
            _cancel_response = True
            await asyncio.sleep(0.05)  # Let any pending sends notice the cancellation
            _cancel_response = False

            voice_state["last_user_time"] = time.time()
            log.info(f"User: {user_text}")
            try:
                await ws.send_json({"type": "status", "state": "thinking"})
            except (WebSocketDisconnect, RuntimeError):
                break

            # Lazy project scan on first message
            global cached_projects
            if not cached_projects:
                try:
                    # Run in executor since scan_projects does sync file I/O
                    loop = asyncio.get_event_loop()
                    cached_projects = await asyncio.wait_for(
                        loop.run_in_executor(None, _scan_projects_sync),
                        timeout=3
                    )
                    log.info(f"Scanned {len(cached_projects)} projects")
                except Exception:
                    cached_projects = []

            try:
                # ── CHECK FOR MODE SWITCHES ──
                t_lower = user_text.lower()

                # ── PLANNING MODE: answering clarifying questions ──
                if planner.is_planning:
                    # Check for bypass
                    if any(p in t_lower for p in BYPASS_PHRASES):
                        plan = planner.active_plan
                        if plan:
                            plan.skipped = True
                            for q in plan.pending_questions[plan.current_question_index:]:
                                if q.get("default") is not None and q["key"] not in plan.answers:
                                    plan.answers[q["key"]] = q["default"]
                        prompt = await planner.build_prompt()
                        name = _generate_project_name(prompt)
                        path = str(Path.home() / "Desktop" / name)
                        os.makedirs(path, exist_ok=True)
                        Path(path, "CLAUDE.md").write_text(prompt)
                        did = dispatch_registry.register(name, path, prompt[:200])
                        asyncio.create_task(_execute_prompt_project(name, prompt, work_session, ws, dispatch_id=did, history=history, voice_state=voice_state))
                        planner.reset()
                        response_text = "Building it now, sir."
                    elif planner.active_plan and planner.active_plan.confirmed is False and planner.active_plan.current_question_index >= len(planner.active_plan.pending_questions):
                        # Confirmation phase
                        result = await planner.handle_confirmation(user_text)
                        if result["confirmed"]:
                            prompt = await planner.build_prompt()
                            name = _generate_project_name(prompt)
                            path = str(Path.home() / "Desktop" / name)
                            os.makedirs(path, exist_ok=True)
                            Path(path, "CLAUDE.md").write_text(prompt)
                            did = dispatch_registry.register(name, path, prompt[:200])
                            asyncio.create_task(_execute_prompt_project(name, prompt, work_session, ws, dispatch_id=did, history=history, voice_state=voice_state))
                            planner.reset()
                            response_text = "On it, sir."
                        elif result["cancelled"]:
                            planner.reset()
                            response_text = "Cancelled, sir."
                        else:
                            response_text = result.get("modification_question", "How shall I adjust the plan, sir?")
                    else:
                        result = await planner.process_answer(user_text, cached_projects)
                        if result["plan_complete"]:
                            response_text = result.get("confirmation_summary", "Ready to build. Shall I proceed, sir?")
                        else:
                            response_text = result.get("next_question", "What else, sir?")

                elif any(w in t_lower for w in ["quit work mode", "exit work mode", "go back to chat", "regular mode", "stop working"]):
                    if work_session.active:
                        await work_session.stop()
                        response_text = "Back to conversation mode, sir."
                    else:
                        response_text = "Already in conversation mode, sir."

                # ── WORK MODE: speech → claude -p → Haiku summary → JARVIS voice ──
                elif work_session.active:
                    if is_casual_question(user_text):
                        # Quick chat — bypass claude -p, use Haiku
                        response_text = await generate_response(
                            user_text, task_manager,
                            cached_projects, history,
                            last_response=last_jarvis_response,
                            session_summary=session_summary,
                        )
                    else:
                        # Send to claude -p (full power)
                        await ws.send_json({"type": "status", "state": "working"})
                        log.info(f"Work mode → claude -p: {user_text[:80]}")

                        full_response = await work_session.send(user_text)

                        # Detect if Claude Code is stalling (asking questions instead of building)
                        if full_response:
                            stall_words = ["which option", "would you prefer", "would you like me to",
                                           "before I proceed", "before proceeding", "should I",
                                           "do you want me to", "let me know", "please confirm",
                                           "which approach", "what would you"]
                            is_stalling = any(w in full_response.lower() for w in stall_words)
                            if is_stalling and work_session._message_count >= 2:
                                # Claude Code keeps asking — push it to build
                                log.info("Claude Code stalling — pushing to build")
                                push_response = await work_session.send(
                                    "Stop asking questions. Use your best judgment and start building now. "
                                    "Write the actual code files. Go with the simplest reasonable approach."
                                )
                                if push_response:
                                    full_response = push_response

                        # Auto-open any localhost URLs Claude Code mentions
                        import re as _re
                        localhost_match = _re.search(r'https?://localhost:\d+', full_response or "")
                        if localhost_match:
                            asyncio.create_task(_execute_browse(localhost_match.group(0)))
                            log.info(f"Auto-opening {localhost_match.group(0)}")

                        # Always summarize work mode responses
                        if full_response:
                            try:
                                response_text = await _llm_call(
                                    f"You are JARVIS reporting to the user ({USER_NAME}). Summarize what happened in 1-2 sentences. "
                                    "Speak in first person -- 'I built', 'I found', 'I set up'. "
                                    "You are talking TO THE USER, not to a coding tool. "
                                    "NEVER give instructions like 'go ahead and build' or 'set up the frontend' -- those are NOT for the user. "
                                    "NEVER say 'Claude Code'. NEVER output [ACTION:...] tags. "
                                    "NEVER read out URLs. No markdown. British precision.",
                                    [{"role": "user", "content": f"Claude Code said:\n{full_response[:2000]}"}],
                                    max_tokens=100,
                                )
                            except Exception:
                                response_text = full_response[:200]
                        else:
                            response_text = full_response

                # ── CHAT MODE: fast keyword detection + Haiku ──
                else:
                    # Check for dismissal/casual remarks first — respond immediately
                    dismissal_response = detect_dismissal_or_casual(user_text)
                    if dismissal_response:
                        response_text = dismissal_response
                    else:
                        action = detect_action_fast(user_text)
                        if action:
                            if action["action"] == "open_terminal":
                                response_text = await handle_open_terminal()
                            elif action["action"] == "show_recent":
                                response_text = await handle_show_recent()
                            elif action["action"] == "describe_screen":
                                response_text = "Taking a look now, sir."
                                asyncio.create_task(_lookup_and_report("screen", _do_screen_lookup, ws, history=history, voice_state=voice_state))
                            elif action["action"] == "open_app":
                                app_name = action.get("target", "")
                                result = await open_app(app_name)
                                response_text = result["confirmation"]
                            elif action["action"] == "check_dispatch":
                                recent = dispatch_registry.get_most_recent()
                                if not recent:
                                    response_text = "No recent builds on record, sir."
                                else:
                                    name = recent["project_name"]
                                    status = recent["status"]
                                    if status == "building" or status == "pending":
                                        elapsed = int(time.time() - recent["updated_at"])
                                        response_text = f"Still working on {name}, sir. Been at it for {elapsed} seconds."
                                    elif status == "completed":
                                        response_text = recent.get("summary") or f"{name} is complete, sir."
                                    elif status in ("failed", "timeout"):
                                        response_text = f"{name} ran into problems, sir."
                                    else:
                                        response_text = f"{name} is {status}, sir."
                            elif action["action"] == "check_tasks":
                                tasks = get_open_tasks()
                                response_text = format_tasks_for_voice(tasks)
                            elif action["action"] == "check_usage":
                                response_text = get_usage_summary()
                            elif action["action"] == "vision_feedback":
                                is_correct = action.get("correct", False)
                                last_q = history[-2]["content"] if len(history) >= 2 else ""
                                if last_q:
                                    asyncio.create_task(vision_agent.feedback(last_q, is_correct))
                                verdict = "noted as correct" if is_correct else "noted — VISION will adjust"
                                response_text = f"Feedback {verdict}, sir."
                            else:
                                response_text = "Understood, sir."
                        else:
                            response_text = await generate_response(
                                    user_text, task_manager,
                                    cached_projects, history,
                                    last_response=last_jarvis_response,
                                    session_summary=session_summary,
                                )

                            # Check for action tags embedded in LLM response
                            clean_response, embedded_action = extract_action(response_text)
                            if embedded_action:
                                log.info(f"LLM embedded action: {embedded_action}")
                                response_text = clean_response
                                # Ensure there's always something to speak
                                if not response_text.strip():
                                    action_type = embedded_action["action"]
                                    if action_type == "prompt_project":
                                        proj = embedded_action["target"].split("|||")[0].strip()
                                        response_text = f"Connecting to {proj} now, sir."
                                    elif action_type == "build":
                                        response_text = "On it, sir."
                                    elif action_type == "research":
                                        response_text = "Looking into that now, sir."
                                    elif action_type == "ask_vision":
                                        response_text = "Consulting VISION, sir."
                                    else:
                                        response_text = "Right away, sir."

                                if embedded_action["action"] == "build":
                                    # Build in background — JARVIS stays conversational
                                    target = embedded_action["target"]
                                    name = _generate_project_name(target)
                                    path = str(Path.home() / "Desktop" / name)
                                    os.makedirs(path, exist_ok=True)

                                    # Write detailed CLAUDE.md
                                    Path(path, "CLAUDE.md").write_text(
                                        f"# Task\n\n{target}\n\n"
                                        "## Instructions\n"
                                        "- BUILD THIS NOW. Do not ask clarifying questions.\n"
                                        "- Use your best judgment for any design/architecture decisions.\n"
                                        "- Write complete, working code files — not plans or specs.\n"
                                        "- If it's a web app: use React + Vite + Tailwind unless specified otherwise.\n"
                                        "- Make it look polished and professional. Modern UI, clean layout.\n"
                                        "- Ensure it runs with a single command (npm run dev or similar).\n"
                                        "- If you reference a real product's UI (e.g. 'Zillow clone'), match their actual layout and features closely.\n"
                                        "- Use realistic mock data, not placeholder Lorem Ipsum.\n"
                                        "- After building, start the dev server and verify the app loads without errors.\n"
                                        "- IMPORTANT: Your LAST line of output MUST be exactly: RUNNING_AT=http://localhost:PORT (the actual port the dev server is using)\n"
                                    )

                                    # Register and dispatch
                                    did = dispatch_registry.register(name, path, target)
                                    asyncio.create_task(
                                        _execute_prompt_project(name, target, work_session, ws, dispatch_id=did, history=history, voice_state=voice_state)
                                    )
                                elif embedded_action["action"] == "browse":
                                    asyncio.create_task(_execute_browse(embedded_action["target"]))
                                elif embedded_action["action"] == "research":
                                    # Research enters work mode too
                                    name = _generate_project_name(embedded_action["target"])
                                    path = str(Path.home() / "Desktop" / name)
                                    os.makedirs(path, exist_ok=True)
                                    await work_session.start(path)
                                    asyncio.create_task(
                                        self_work_and_notify(work_session, embedded_action["target"], ws)
                                    )
                                elif embedded_action["action"] == "open_terminal":
                                    asyncio.create_task(_execute_open_terminal())
                                elif embedded_action["action"] == "prompt_project":
                                    target = embedded_action["target"]
                                    if "|||" in target:
                                        proj_name, _, prompt = target.partition("|||")
                                        proj_name = proj_name.strip()
                                        prompt = prompt.strip()
                                        # Check for recent completed dispatch before re-dispatching
                                        recent = dispatch_registry.get_recent_for_project(proj_name)
                                        if recent and recent.get("summary"):
                                            log.info(f"Using recent dispatch result for {proj_name} instead of re-dispatching")
                                            response_text = recent["summary"]
                                            history.append({"role": "assistant", "content": f"[Previous dispatch result for {proj_name}]: {recent['summary']}"})
                                        else:
                                            asyncio.create_task(
                                                _execute_prompt_project(proj_name, prompt, work_session, ws, history=history, voice_state=voice_state)
                                            )
                                    else:
                                        log.warning(f"PROMPT_PROJECT missing ||| delimiter: {target}")
                                elif embedded_action["action"] == "add_task":
                                    target = embedded_action["target"]
                                    parts = target.split("|||")
                                    if len(parts) >= 2:
                                        priority = parts[0].strip() or "medium"
                                        title = parts[1].strip()
                                        desc = parts[2].strip() if len(parts) > 2 else ""
                                        due = parts[3].strip() if len(parts) > 3 else ""
                                        create_task(title=title, description=desc, priority=priority, due_date=due)
                                        log.info(f"Task created: {title}")
                                elif embedded_action["action"] == "add_note":
                                    target = embedded_action["target"]
                                    if "|||" in target:
                                        topic, _, content = target.partition("|||")
                                        create_note(content=content.strip(), topic=topic.strip())
                                    else:
                                        create_note(content=target)
                                    log.info(f"Note created")
                                elif embedded_action["action"] == "complete_task":
                                    try:
                                        task_id = int(embedded_action["target"].strip())
                                        complete_task(task_id)
                                        log.info(f"Task {task_id} completed")
                                    except ValueError:
                                        pass
                                elif embedded_action["action"] == "remember":
                                    remember(embedded_action["target"].strip(), mem_type="fact", importance=7)
                                    log.info(f"Memory stored: {embedded_action['target'][:60]}")
                                elif embedded_action["action"] == "ask_vision":
                                    question = embedded_action["target"].strip()
                                    if not response_text.strip():
                                        response_text = "One moment, sir."
                                    _AGENT_STATES["vision"]["usage"] = 80
                                    try:
                                        vision_resp = await vision_agent.ask(question)
                                        if vision_resp.confidence != "uncertain":
                                            response_text = vision_resp.answer
                                        else:
                                            response_text = vision_resp.answer
                                    except Exception as _ve:
                                        log.error(f"VISION call failed: {_ve}")
                                        response_text = "I'm afraid VISION is unavailable at the moment, sir."
                                    finally:
                                        _AGENT_STATES["vision"]["usage"] = vision_agent.get_status()["usage"]
                                    log.info(f"VISION answered: {response_text[:80]}")
                                elif embedded_action["action"] == "open_app":
                                    app_target = embedded_action["target"].strip()
                                    asyncio.create_task(_execute_open_app(app_target))
                                elif embedded_action["action"] == "screen":
                                    asyncio.create_task(_lookup_and_report("screen", _do_screen_lookup, ws, history=history, voice_state=voice_state))

                # Update history
                history.append({"role": "user", "content": user_text})
                history.append({"role": "assistant", "content": response_text})

                # Three-tier memory: also track in session buffer
                session_buffer.append({"role": "user", "content": user_text})
                session_buffer.append({"role": "assistant", "content": response_text})

                # Check if rolling summary needs updating
                messages_since_last_summary += 1
                if messages_since_last_summary >= 5 and len(history) > 20 and not summary_update_pending:
                    summary_update_pending = True
                    messages_since_last_summary = 0
                    # Get messages that are about to be rotated out
                    rotated = history[:-20] if len(history) > 20 else []
                    if rotated:
                        async def _do_summary():
                            nonlocal session_summary, summary_update_pending
                            session_summary = await _update_session_summary(
                                session_summary, rotated
                            )
                            summary_update_pending = False
                        asyncio.create_task(_do_summary())
                    else:
                        summary_update_pending = False

                # Extract memories in background — only when exchange looks factual.
                # Skip for short chitchat to avoid burning API rate limits needlessly.
                _memory_triggers = ["my ", "i am ", "i'm ", "i work", "i like", "i want",
                                     "remember", "don't forget", "note that", "always ",
                                     "never ", "prefer", "name is", "called "]
                _should_remember = len(user_text) > 30 and any(t in user_text.lower() for t in _memory_triggers)
                if _should_remember:
                    asyncio.create_task(extract_memories(user_text, response_text))

                # TTS — translate back and use native voice if session is multilingual
                tts = strip_markdown_for_tts(response_text)
                tts_voice: Optional[str] = None
                if _session_lang:
                    tts = translate(tts, "en", _session_lang)
                    tts_voice = get_voice(_session_lang)
                    log.info(f"Multilingual TTS [{get_language_name(_session_lang)}] voice={tts_voice}")

                try:
                    await ws.send_json({"type": "status", "state": "speaking"})
                except (WebSocketDisconnect, RuntimeError):
                    log.debug("Client disconnected before TTS — aborting response")
                    break
                audio = await synthesize_speech(tts, voice=tts_voice)
                try:
                    if audio:
                        await ws.send_json({"type": "audio", "data": base64.b64encode(audio).decode(), "text": response_text})
                    else:
                        await ws.send_json({"type": "text", "text": response_text})
                        await ws.send_json({"type": "status", "state": "idle"})
                except (WebSocketDisconnect, RuntimeError):
                    log.debug("Client disconnected while sending audio — moving on")
                    break
                log.info(f"JARVIS: {response_text}")
                last_jarvis_response = response_text

            except (WebSocketDisconnect, RuntimeError) as e:
                # Client navigated away or closed tab — exit cleanly, no error spam
                log.debug(f"WebSocket gone mid-response: {type(e).__name__}")
                break
            except Exception as e:
                log.error(f"Error: {e}", exc_info=True)
                try:
                    fallback = "Something went wrong, sir."
                    audio = await synthesize_speech(fallback)
                    if audio:
                        await ws.send_json({"type": "audio", "data": base64.b64encode(audio).decode(), "text": fallback})
                    else:
                        await ws.send_json({"type": "audio", "data": "", "text": fallback})
                except (WebSocketDisconnect, RuntimeError):
                    pass  # Client gone — that's fine
                except Exception:
                    pass

    except WebSocketDisconnect:
        log.info("Voice WebSocket disconnected")
    except RuntimeError as e:
        # "WebSocket is not connected" — client closed tab, not a real error
        log.debug(f"WebSocket RuntimeError (client gone): {e}")
    except Exception as e:
        log.error(f"WebSocket error: {e}", exc_info=True)
    finally:
        task_manager.unregister_websocket(ws)


# ---------------------------------------------------------------------------
# Settings / Configuration endpoints
# ---------------------------------------------------------------------------

def _env_file_path() -> Path:
    return Path(__file__).parent / ".env"

def _env_example_path() -> Path:
    return Path(__file__).parent / ".env.example"

def _read_env() -> tuple[list[str], dict[str, str]]:
    """Read .env file. Returns (raw_lines, parsed_dict). Creates from .env.example if missing."""
    path = _env_file_path()
    if not path.exists():
        example = _env_example_path()
        if example.exists():
            import shutil as _shutil
            _shutil.copy2(str(example), str(path))
        else:
            path.write_text("")
    lines = path.read_text().splitlines()
    parsed: dict[str, str] = {}
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            k, _, v = stripped.partition("=")
            parsed[k.strip()] = v.strip().strip('"').strip("'")
    return lines, parsed

def _write_env_key(key: str, value: str) -> None:
    """Update a single key in .env, preserving comments and order."""
    lines, _ = _read_env()
    found = False
    new_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            k, _, _ = stripped.partition("=")
            if k.strip() == key:
                new_lines.append(f"{key}={value}")
                found = True
                continue
        new_lines.append(line)
    if not found:
        new_lines.append(f"{key}={value}")
    _env_file_path().write_text("\n".join(new_lines) + "\n")
    os.environ[key] = value

class KeyUpdate(BaseModel):
    key_name: str
    key_value: str

class KeyTest(BaseModel):
    key_value: str | None = None

class PreferencesUpdate(BaseModel):
    user_name: str = ""
    honorific: str = "sir"
    orb_color: str = "#4ca8e8"

@app.get("/api/settings/status")
async def api_settings_status():
    try:
        from memory import _get_db
        conn = _get_db()
        mem_count = conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
        task_count = conn.execute("SELECT COUNT(*) FROM tasks WHERE done=0").fetchone()[0]
        conn.close()
    except:
        mem_count = 0
        task_count = 0

    import shutil
    return {
        "claude_code_installed": bool(shutil.which("claude")),
        "memory_count": mem_count,
        "task_count": task_count,
        "server_port": 8340,
        "uptime_seconds": int(time.time() - _server_start_time),
    }

@app.get("/api/settings/preferences")
async def api_settings_preferences():
    return {
        "user_name": os.getenv("USER_NAME", "sir"),
        "honorific": os.getenv("HONORIFIC", "sir"),
        "orb_color": os.getenv("ORB_COLOR", "#4ca8e8"),
    }

@app.post("/api/settings/preferences")
async def api_settings_preferences_post(body: PreferencesUpdate):
    if body.user_name:
        _write_env_key("USER_NAME", body.user_name)
    if body.honorific:
        _write_env_key("HONORIFIC", body.honorific)
    if body.orb_color:
        _write_env_key("ORB_COLOR", body.orb_color)
    return {"success": True}

@app.post("/api/settings/keys")
async def api_settings_keys(body: KeyUpdate):
    allowed = {"USER_NAME", "HONORIFIC", "CALENDAR_ACCOUNTS", "OLLAMA_API_KEY", "OLLAMA_MODEL", "EDGE_TTS_VOICE"}
    if body.key_name not in allowed:
        return JSONResponse({"success": False, "error": "Invalid key name"}, status_code=400)
    _write_env_key(body.key_name, body.key_value)
    return {"success": True}

@app.post("/api/synthesize")
async def api_synthesize(body: dict):
    """Synthesize speech for voice preview."""
    text = body.get("text", "Testing voice synthesis.")
    audio_bytes = await synthesize_speech(text)
    if audio_bytes:
        encoded = base64.b64encode(audio_bytes).decode()
        return {"audio": encoded}
    return {"error": "Synthesis failed"}, 500

@app.post("/api/settings/agents")
async def api_settings_agents(body: dict):
    """Save multi-agent configuration."""
    agents = body.get("agents", {})
    # Store in memory or .env as needed
    # For now, just acknowledge receipt
    log.info(f"Agent configuration: {agents}")
    return {"success": True}

@app.post("/api/settings/test-llm")
async def api_test_llm(body: KeyTest):
    try:
        result = await _llm_call("", [{"role": "user", "content": "Hi"}], max_tokens=10)
        return {"valid": bool(result), "response": result}
    except Exception as e:
        return {"valid": False, "error": str(e)}


@app.post("/api/fix-self")
async def api_fix_self():
    """Enter work mode in the JARVIS repo — JARVIS can now fix himself."""
    jarvis_dir = str(Path(__file__).parent)
    # Open a terminal in the JARVIS directory with Claude Code running
    result = await open_claude_in_project(jarvis_dir, "Review this JARVIS project and help fix any issues.")
    log.info(f"Work mode: JARVIS repo opened for self-improvement — {result['confirmation']}")
    return {"status": "work_mode_active", "path": jarvis_dir}


# ---------------------------------------------------------------------------
# System stats + Agent status endpoints
# ---------------------------------------------------------------------------

try:
    import psutil as _psutil
    _PSUTIL_OK = True
except ImportError:
    _PSUTIL_OK = False
    log.warning("psutil not installed — /api/system/stats will return zeros. Run: pip install psutil")

@app.get("/api/system/stats")
async def api_system_stats():
    """Real-time PC hardware stats for the HUD telemetry panel."""
    if not _PSUTIL_OK:
        return {"cpu": 0, "memory": 0, "memory_label": "?/? GB",
                "disk": 0, "disk_label": "?/? GB", "available": False}
    cpu  = _psutil.cpu_percent(interval=0.1)
    mem  = _psutil.virtual_memory()
    disk = _psutil.disk_usage('/')
    return {
        "available": True,
        "cpu":          round(cpu, 1),
        "memory":       round(mem.percent, 1),
        "memory_label": f"{mem.used/(1024**3):.1f}/{mem.total/(1024**3):.1f} GB",
        "disk":         round(disk.percent, 1),
        "disk_label":   f"{disk.used/(1024**3):.0f}/{disk.total/(1024**3):.0f} GB",
    }

# Agent states — VISION is active; others are offline placeholders
_AGENT_STATES: dict = {
    "ultron": {"online": False, "usage": 0},
    "echo":   {"online": False, "usage": 0},
    "friday": {"online": False, "usage": 0},
    "vision": {"online": True,  "usage": 0},
}

@app.get("/api/agents/status")
async def api_agents_status():
    """Returns online/offline + usage% for each named agent."""
    _AGENT_STATES["vision"] = vision_agent.get_status()
    return _AGENT_STATES

# ---------------------------------------------------------------------------
# Static file serving (frontend)
# ---------------------------------------------------------------------------

from starlette.staticfiles import StaticFiles
from starlette.responses import FileResponse

FRONTEND_DIST = Path(__file__).parent / "frontend" / "dist"

if FRONTEND_DIST.exists():
    @app.get("/")
    async def serve_index():
        return FileResponse(str(FRONTEND_DIST / "index.html"))

    app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIST / "assets")), name="assets")


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse
    import uvicorn

    parser = argparse.ArgumentParser(description="JARVIS Server")
    parser.add_argument("--host", default="0.0.0.0", help="Bind host")
    parser.add_argument("--port", type=int, default=8340, help="Bind port")
    parser.add_argument("--reload", action="store_true", help="Auto-reload on changes")
    parser.add_argument("--ssl", action="store_true", help="Enable HTTPS with key.pem/cert.pem")
    args = parser.parse_args()

    # Auto-detect SSL certs
    cert_file = Path(__file__).parent / "cert.pem"
    key_file = Path(__file__).parent / "key.pem"
    use_ssl = args.ssl or (cert_file.exists() and key_file.exists())

    proto = "https" if use_ssl else "http"
    ws_proto = "wss" if use_ssl else "ws"

    print()
    print("  J.A.R.V.I.S. Server v0.1.0")
    print(f"  WebSocket: {ws_proto}://{args.host}:{args.port}/ws/voice")
    print(f"  REST API:  {proto}://{args.host}:{args.port}/api/")
    print(f"  Tasks:     {proto}://{args.host}:{args.port}/api/tasks")
    print()

    ssl_kwargs = {}
    if use_ssl:
        ssl_kwargs["ssl_keyfile"] = str(key_file)
        ssl_kwargs["ssl_certfile"] = str(cert_file)

    uvicorn.run(
        "server:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="info",
        **ssl_kwargs,
    )
