/**
 * JARVIS (Just A Rather Very Intelligent System) — Main entry point.
 *
 * Wires together the orb visualization, WebSocket communication,
 * speech recognition, and audio playback into a single experience.
 */

import { createOrb, type OrbState } from "./orb";
import { createVoiceInput, createAudioPlayer } from "./voice";
import { createSocket } from "./ws";
import { openSettings, checkFirstTimeSetup } from "./settings";
import "./style.css";

// Initialize orb color from localStorage and apply to both orb + HUD
function applyHudColor(hex: string) {
  document.documentElement.style.setProperty("--orb-color", hex);
  document.documentElement.style.setProperty("--primary", hex);
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  const glow = `rgba(${r},${g},${b},0.55)`;
  document.documentElement.style.setProperty("--primary-glow", glow);
  document.documentElement.style.setProperty("--glow-sm", `0 0 8px ${glow}`);
  document.documentElement.style.setProperty("--glow-md", `0 0 16px ${glow}, 0 0 2px ${hex}`);
}

const savedColor = localStorage.getItem("jarvis-orb-color") || "#00d4ff";
applyHudColor(savedColor);

// ---------------------------------------------------------------------------
// State machine
// ---------------------------------------------------------------------------

type State = "idle" | "listening" | "thinking" | "speaking";
let currentState: State = "idle";
let isMuted = false;

const statusEl = document.getElementById("status-text")!;
const errorEl = document.getElementById("error-text")!;

function showError(msg: string) {
  errorEl.textContent = msg;
  errorEl.style.opacity = "1";
  setTimeout(() => {
    errorEl.style.opacity = "0";
  }, 5000);
}

const orbStateEl = document.getElementById("orb-state-label")!;
const btnMuteEl = document.getElementById("btn-mute")!;

function updateStatus(state: State) {
  const labels: Record<State, string> = {
    idle: "",
    listening: "listening",
    thinking: "thinking",
    speaking: "",
  };
  statusEl.textContent = labels[state];
  orbStateEl.textContent = labels[state];

  // Mic button pulses while listening
  btnMuteEl.classList.toggle("listening", state === "listening" && !isMuted);
}

// ---------------------------------------------------------------------------
// Init components
// ---------------------------------------------------------------------------

const canvas = document.getElementById("orb-canvas") as HTMLCanvasElement;
const orb = createOrb(canvas);

// Expose setOrbColor globally so settings panel can update orb + HUD color
(window as any).setOrbColor = (hex: string) => {
  orb.setColor(hex);
  applyHudColor(hex);
};

const wsProto = window.location.protocol === "https:" ? "wss:" : "ws:";
const WS_URL = `${wsProto}//${window.location.host}/ws/voice`;
const socket = createSocket(WS_URL);

const audioPlayer = createAudioPlayer();
orb.setAnalyser(audioPlayer.getAnalyser());

function transition(newState: State) {
  if (newState === currentState) return;
  currentState = newState;
  orb.setState(newState as OrbState);
  updateStatus(newState);

  switch (newState) {
    case "idle":
      if (!isMuted) voiceInput.resume();
      break;
    case "listening":
      if (!isMuted) voiceInput.resume();
      break;
    case "thinking":
      voiceInput.pause();
      break;
    case "speaking":
      voiceInput.pause();
      break;
  }
}

// ---------------------------------------------------------------------------
// Voice input
// ---------------------------------------------------------------------------

const voiceInput = createVoiceInput(
  (text: string) => {
    // Cancel any current JARVIS response before sending new input
    audioPlayer.stop();
    // User spoke — send transcript
    socket.send({ type: "transcript", text, isFinal: true });
    transition("thinking");
  },
  (msg: string) => {
    showError(msg);
  }
);

// ---------------------------------------------------------------------------
// Audio playback finished
// ---------------------------------------------------------------------------

audioPlayer.onFinished(() => {
  transition("idle");
});

// ---------------------------------------------------------------------------
// WebSocket messages
// ---------------------------------------------------------------------------

socket.onMessage((msg) => {
  const type = msg.type as string;

  if (type === "audio") {
    const audioData = msg.data as string;
    console.log("[audio] received", audioData ? `${audioData.length} chars` : "EMPTY", "state:", currentState);
    if (audioData) {
      if (currentState !== "speaking") {
        transition("speaking");
      }
      audioPlayer.enqueue(audioData);
    } else {
      // TTS failed — no audio but still need to return to idle
      console.warn("[audio] no data received, returning to idle");
      transition("idle");
    }
    // Log text for debugging
    if (msg.text) console.log("[JARVIS]", msg.text);
  } else if (type === "status") {
    const state = msg.state as string;
    if (state === "thinking" && currentState !== "thinking") {
      transition("thinking");
    } else if (state === "working") {
      // Task spawned — show thinking with a different label
      transition("thinking");
      statusEl.textContent = "working...";
    } else if (state === "idle") {
      transition("idle");
    }
  } else if (type === "text") {
    // Text fallback when TTS fails
    console.log("[JARVIS]", msg.text);
  } else if (type === "task_spawned") {
    console.log("[task]", "spawned:", msg.task_id, msg.prompt);
  } else if (type === "task_complete") {
    console.log("[task]", "complete:", msg.task_id, msg.status, msg.summary);
  }
});

// ---------------------------------------------------------------------------
// Kick off
// ---------------------------------------------------------------------------

// Start listening after a brief delay for the orb to render
setTimeout(() => {
  voiceInput.start();
  transition("listening");
}, 1000);

// Resume AudioContext on ANY user interaction (browser autoplay policy)
function ensureAudioContext() {
  const ctx = audioPlayer.getAnalyser().context as AudioContext;
  if (ctx.state === "suspended") {
    ctx.resume().then(() => console.log("[audio] context resumed"));
  }
}
document.addEventListener("click", ensureAudioContext);
document.addEventListener("touchstart", ensureAudioContext);
document.addEventListener("keydown", ensureAudioContext, { once: true });

// Try to resume audio context on load
ensureAudioContext();

// ---------------------------------------------------------------------------
// UI Controls
// ---------------------------------------------------------------------------

const btnMute = document.getElementById("btn-mute")!;
const btnMenu = document.getElementById("btn-menu")!;
const menuDropdown = document.getElementById("menu-dropdown")!;
const btnRestart = document.getElementById("btn-restart")!;
const btnFixSelf = document.getElementById("btn-fix-self")!;

btnMute.addEventListener("click", (e) => {
  e.stopPropagation();
  isMuted = !isMuted;
  btnMute.classList.toggle("muted", isMuted);
  if (isMuted) {
    voiceInput.pause();
    transition("idle");
  } else {
    voiceInput.resume();
    transition("listening");
  }
});

btnMenu.addEventListener("click", (e) => {
  e.stopPropagation();
  menuDropdown.style.display = menuDropdown.style.display === "none" ? "block" : "none";
});

document.addEventListener("click", () => {
  menuDropdown.style.display = "none";
});

btnRestart.addEventListener("click", async (e) => {
  e.stopPropagation();
  menuDropdown.style.display = "none";
  statusEl.textContent = "restarting...";
  try {
    await fetch("/api/restart", { method: "POST" });
    // Wait a few seconds then reload
    setTimeout(() => window.location.reload(), 4000);
  } catch {
    statusEl.textContent = "restart failed";
  }
});

btnFixSelf.addEventListener("click", (e) => {
  e.stopPropagation();
  menuDropdown.style.display = "none";
  // Activate work mode on the WebSocket session (JARVIS becomes Claude Code's voice)
  socket.send({ type: "fix_self" });
  statusEl.textContent = "entering work mode...";
});

// Settings button
const btnSettings = document.getElementById("btn-settings")!;
btnSettings.addEventListener("click", (e) => {
  e.stopPropagation();
  menuDropdown.style.display = "none";
  openSettings();
});

// First-time setup detection — check after a short delay for server readiness
setTimeout(() => {
  checkFirstTimeSetup();
}, 2000);

// ---------------------------------------------------------------------------
// HUD — clock, greeting, metrics, reactor, quick launch, uptime
// ---------------------------------------------------------------------------

// Clock
const hudTimeEl = document.getElementById("hud-time")!;
const hudDateEl = document.getElementById("hud-date")!;
const greetingEl = document.getElementById("greeting-text")!;

const DAYS   = ["SUN","MON","TUE","WED","THU","FRI","SAT"];
const MONTHS = ["JAN","FEB","MAR","APR","MAY","JUN","JUL","AUG","SEP","OCT","NOV","DEC"];

function getGreeting(): string {
  const h = new Date().getHours();
  if (h >= 5  && h < 12) return "GOOD MORNING, SIR";
  if (h >= 12 && h < 17) return "GOOD AFTERNOON, SIR";
  if (h >= 17 && h < 21) return "GOOD EVENING, SIR";
  return "GOOD NIGHT, SIR";
}

function tickClock() {
  const now = new Date();
  const hh = now.getHours().toString().padStart(2, "0");
  const mm = now.getMinutes().toString().padStart(2, "0");
  const ss = now.getSeconds().toString().padStart(2, "0");
  hudTimeEl.textContent = `${hh}:${mm}:${ss}`;
  hudDateEl.textContent = `${DAYS[now.getDay()]}, ${MONTHS[now.getMonth()]} ${now.getDate()}`;
  greetingEl.innerHTML = `${getGreeting()} · <span class="greeting-hl">HOW MAY I ASSIST</span>`;
}
tickClock();
setInterval(tickClock, 1000);

// Metrics simulation
interface Metrics { cpu: number; memory: number; signal: number; gpu: number; }
let metrics: Metrics = { cpu: 67, memory: 73, signal: 91, gpu: 82 };

const cpuArcEl    = document.getElementById("gauge-cpu-arc") as SVGCircleElement | null;
const cpuValEl    = document.getElementById("cpu-val")!;
const gpuValEl    = document.getElementById("gpu-val")!;
const barMemEl    = document.getElementById("bar-memory") as HTMLElement | null;
const valMemEl    = document.getElementById("val-memory")!;
const barSigEl    = document.getElementById("bar-signal") as HTMLElement | null;
const valSigEl    = document.getElementById("val-signal")!;

function updateMetrics() {
  const clamp = (v: number) => Math.max(0, Math.min(100, v));
  metrics.cpu    = clamp(metrics.cpu    + (Math.random() - 0.5) * 10);
  metrics.memory = clamp(metrics.memory + (Math.random() - 0.5) * 5);
  metrics.signal = clamp(metrics.signal + (Math.random() - 0.5) * 8);

  cpuValEl.textContent = String(Math.round(metrics.cpu));
  gpuValEl.textContent = String(Math.round(metrics.gpu));
  valMemEl.textContent = `${Math.round(metrics.memory)}%`;
  valSigEl.textContent = `${Math.round(metrics.signal)}%`;

  // CPU arc: strokeDashoffset = -(152 * (1 - cpu/100))
  if (cpuArcEl) cpuArcEl.style.strokeDashoffset = `-${152 * (1 - metrics.cpu / 100)}`;
  if (barMemEl) barMemEl.style.width = `${metrics.memory}%`;
  if (barSigEl) barSigEl.style.width = `${metrics.signal}%`;
}
setInterval(updateMetrics, 3000);

// Reactor animation
let reactorCharge = 100;
let reactorOnline = true;

const rRing1  = document.getElementById("r-ring1");
const rRing2  = document.getElementById("r-ring2");
const rRing3  = document.getElementById("r-ring3");
const rSpin1  = document.getElementById("r-spin1");
const rSpin2  = document.getElementById("r-spin2");
const rOuter  = document.getElementById("r-outer");
const rCore   = document.getElementById("r-core");
const rCenter = document.getElementById("r-center");
const rCoreFill = document.getElementById("r-core-fill");
const reactorOnlineEl  = document.getElementById("reactor-online-text")!;
const reactorPctEl     = document.getElementById("reactor-pct")!;

function setReactorAttr(el: Element | null, attr: string, val: string) {
  if (el) el.setAttribute(attr, val);
}

function tickReactor() {
  const step = 40; // ms per tick
  if (reactorOnline) {
    if (reactorCharge >= 100) {
      setTimeout(() => { reactorOnline = false; }, 1500);
      return;
    }
    let speed = reactorCharge < 20 ? 0.5 : reactorCharge < 80 ? 3 + (reactorCharge - 20) / 10 : 2 - (reactorCharge - 80) / 20;
    reactorCharge = Math.min(100, reactorCharge + speed);
  } else {
    if (reactorCharge <= 0) {
      setTimeout(() => { reactorOnline = true; }, 1500);
      return;
    }
    let speed = reactorCharge > 80 ? 4 : reactorCharge > 40 ? 2.5 : reactorCharge > 10 ? 1.5 : 0.3;
    reactorCharge = Math.max(0, reactorCharge - speed);
  }

  const pct = reactorCharge / 100;

  // Update text
  reactorOnlineEl.textContent = reactorOnline ? "● ONLINE" : "○ OFFLINE";
  reactorOnlineEl.className = reactorOnline ? "reactor-online" : "reactor-online offline";
  reactorPctEl.textContent = `${Math.round(reactorCharge)}%`;
  reactorPctEl.style.color = reactorCharge > 50 ? "var(--primary)" : "var(--accent)";

  // Charging rings dashoffset
  setReactorAttr(rRing1, "stroke-dashoffset", String(176 * (1 - pct)));
  setReactorAttr(rRing2, "stroke-dashoffset", String(138 * (1 - pct)));
  setReactorAttr(rRing3, "stroke-dashoffset", String(100 * (1 - pct)));

  // Outer ring opacity
  if (rOuter) (rOuter as SVGCircleElement).setAttribute("opacity", String(reactorOnline ? 0.9 : 0.3));

  // Spinning rings — visible while charging
  const spinning = reactorOnline && reactorCharge < 100;
  if (rSpin1) (rSpin1 as SVGCircleElement).style.opacity = spinning ? "0.7" : "0";
  if (rSpin2) (rSpin2 as SVGCircleElement).style.opacity = spinning ? "0.5" : "0";

  // Core glow
  const coreFilter = `drop-shadow(0 0 ${reactorOnline ? 8 + pct * 20 : 1}px var(--primary-glow))`;
  if (rCore) (rCore as SVGCircleElement).style.filter = coreFilter;
  if (rCore) (rCore as SVGCircleElement).setAttribute("opacity", String(reactorOnline ? 0.6 + pct * 0.4 : 0.15));
  if (rCenter) (rCenter as SVGCircleElement).style.filter = `drop-shadow(0 0 ${reactorOnline ? 12 + pct * 20 : 2}px var(--primary-glow))`;
  if (rCoreFill) (rCoreFill as SVGCircleElement).setAttribute("opacity", String(reactorOnline ? 0.1 + pct * 0.3 : 0.02));
}
setInterval(tickReactor, 40);

// Uptime + network status from server
async function refreshStatus() {
  try {
    const res = await fetch("/api/settings/status");
    const data = await res.json();
    const secs = data.uptime_seconds as number || 0;
    const days = Math.floor(secs / 86400);
    const hrs  = Math.floor((secs % 86400) / 3600);
    const mins = Math.floor((secs % 3600) / 60);
    const uptimeEl = document.getElementById("diag-uptime");
    if (uptimeEl) uptimeEl.textContent = `${days}D ${hrs}H ${mins}M`;
    const netEl = document.getElementById("diag-network");
    if (netEl) netEl.textContent = "OPTIMAL";
  } catch {
    const netEl = document.getElementById("diag-network");
    if (netEl) netEl.textContent = "OFFLINE";
  }
}
refreshStatus();
setInterval(refreshStatus, 60_000);

// Quick launch hex buttons
document.querySelectorAll<HTMLButtonElement>(".hex-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    const cmd = btn.dataset.cmd;
    if (!cmd) return;
    audioPlayer.stop();
    socket.send({ type: "transcript", text: cmd, isFinal: true });
    transition("thinking");
  });
});
