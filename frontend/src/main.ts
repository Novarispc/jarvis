/**
 * JARVIS — Main entry point.
 */

import { createOrb, type OrbState } from "./orb";
import { createVoiceInput, createAudioPlayer } from "./voice";
import { createSocket } from "./ws";
import { openSettings, checkFirstTimeSetup } from "./settings";
import "./style.css";

// Apply HUD color from localStorage
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

function applyOrbTextColor(hex: string) {
  document.documentElement.style.setProperty("--orb-text-color", hex);
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  document.documentElement.style.setProperty("--orb-text-glow", `rgba(${r},${g},${b},0.55)`);
}
const savedTextColor = localStorage.getItem("jarvis-orb-text-color") || "#00d4ff";
applyOrbTextColor(savedTextColor);
(window as any).setOrbTextColor = applyOrbTextColor;

// ---------------------------------------------------------------------------
// State machine
// ---------------------------------------------------------------------------

type State = "idle" | "listening" | "thinking" | "speaking";
let currentState: State = "idle";
let isMuted = false;

const statusEl  = document.getElementById("status-text")!;
const errorEl   = document.getElementById("error-text")!;

function showError(msg: string) {
  errorEl.textContent = msg;
  errorEl.style.opacity = "1";
  setTimeout(() => { errorEl.style.opacity = "0"; }, 5000);
}

const orbStateEl = document.getElementById("orb-state-label")!;
const btnMuteEl  = document.getElementById("btn-mute")!;

function updateStatus(state: State) {
  const labels: Record<State, string> = {
    idle: "", listening: "listening", thinking: "thinking", speaking: "",
  };
  statusEl.textContent    = labels[state];
  orbStateEl.textContent  = labels[state];
  btnMuteEl.classList.toggle("listening", state === "listening" && !isMuted);
}

// ---------------------------------------------------------------------------
// Init components
// ---------------------------------------------------------------------------

const canvas = document.getElementById("orb-canvas") as HTMLCanvasElement;
const orb    = createOrb(canvas);

(window as any).setOrbColor = (hex: string) => {
  orb.setColor(hex);
  applyHudColor(hex);
};

const wsProto = window.location.protocol === "https:" ? "wss:" : "ws:";
const WS_URL  = `${wsProto}//${window.location.host}/ws/voice`;
const socket  = createSocket(WS_URL);
// Expose send for settings panel (fix-self action)
(window as any).__jarvisSend = socket.send.bind(socket);

const audioPlayer = createAudioPlayer();
orb.setAnalyser(audioPlayer.getAnalyser());

function transition(newState: State) {
  if (newState === currentState) return;
  currentState = newState;
  orb.setState(newState as OrbState);
  updateStatus(newState);

  switch (newState) {
    case "idle":
    case "listening":
      if (!isMuted) voiceInput.resume();
      break;
    case "thinking":
    case "speaking":
      voiceInput.pause();
      break;
  }
}

// ---------------------------------------------------------------------------
// Voice input
// ---------------------------------------------------------------------------

const voiceInput = createVoiceInput(
  (text: string, lang: string) => {
    audioPlayer.stop();
    socket.send({ type: "transcript", text, lang, isFinal: true });
    transition("thinking");
  },
  (msg: string) => { showError(msg); }
);

audioPlayer.onFinished(() => { transition("idle"); });

// ---------------------------------------------------------------------------
// WebSocket messages
// ---------------------------------------------------------------------------

socket.onMessage((msg) => {
  const type = msg.type as string;

  if (type === "audio") {
    const audioData = msg.data as string;
    if (audioData) {
      if (currentState !== "speaking") transition("speaking");
      audioPlayer.enqueue(audioData);
    } else {
      transition("idle");
    }
    if (msg.text) console.log("[JARVIS]", msg.text);
  } else if (type === "status") {
    const state = msg.state as string;
    if (state === "thinking" && currentState !== "thinking") {
      transition("thinking");
    } else if (state === "working") {
      transition("thinking");
      statusEl.textContent = "working...";
    } else if (state === "idle") {
      transition("idle");
    }
  } else if (type === "text") {
    console.log("[JARVIS]", msg.text);
  } else if (type === "task_spawned") {
    console.log("[task] spawned:", msg.task_id, msg.prompt);
  } else if (type === "task_complete") {
    console.log("[task] complete:", msg.task_id, msg.status, msg.summary);
  }
});

// ---------------------------------------------------------------------------
// Kick off
// ---------------------------------------------------------------------------

setTimeout(() => {
  voiceInput.start();
  transition("listening");
}, 1000);

function ensureAudioContext() {
  const ctx = audioPlayer.getAnalyser().context as AudioContext;
  if (ctx.state === "suspended") ctx.resume();
}
document.addEventListener("click", ensureAudioContext);
document.addEventListener("touchstart", ensureAudioContext);
document.addEventListener("keydown", ensureAudioContext, { once: true });
ensureAudioContext();

// ---------------------------------------------------------------------------
// UI Controls — header buttons
// ---------------------------------------------------------------------------

const btnMute = document.getElementById("btn-mute")!;
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

const btnSettingsOpen = document.getElementById("btn-settings-open")!;
btnSettingsOpen.addEventListener("click", (e) => {
  e.stopPropagation();
  closeAllDrawers();
  openSettings();
});

// ---------------------------------------------------------------------------
// HUD — clock
// ---------------------------------------------------------------------------

const hudTimeEl  = document.getElementById("hud-time")!;
const hudDateEl  = document.getElementById("hud-date")!;

const DAYS   = ["SUN","MON","TUE","WED","THU","FRI","SAT"];
const MONTHS = ["JAN","FEB","MAR","APR","MAY","JUN","JUL","AUG","SEP","OCT","NOV","DEC"];

function tickClock() {
  const now = new Date();
  const hh  = now.getHours().toString().padStart(2, "0");
  const mm  = now.getMinutes().toString().padStart(2, "0");
  const ss  = now.getSeconds().toString().padStart(2, "0");
  hudTimeEl.textContent = `${hh}:${mm}:${ss}`;
  hudDateEl.textContent = `${DAYS[now.getDay()]}, ${MONTHS[now.getMonth()]} ${now.getDate()}`;
}
tickClock();
setInterval(tickClock, 1000);

// ---------------------------------------------------------------------------
// System Telemetry — real PC stats via /api/system/stats
// ---------------------------------------------------------------------------

const cpuArcEl  = document.getElementById("gauge-cpu-arc") as SVGCircleElement | null;
const ramArcEl  = document.getElementById("gauge-ram-arc") as SVGCircleElement | null;
const cpuValEl  = document.getElementById("cpu-val")!;
const ramValEl  = document.getElementById("ram-val")!;
const barCpuEl  = document.getElementById("bar-cpu")  as HTMLElement | null;
const barMemEl  = document.getElementById("bar-memory") as HTMLElement | null;
const barDiskEl = document.getElementById("bar-disk")  as HTMLElement | null;
const valCpuBar = document.getElementById("val-cpu-bar")!;
const valMemEl  = document.getElementById("val-memory")!;
const valDiskEl = document.getElementById("val-disk")!;

function setArcOffset(el: SVGCircleElement | null, pct: number) {
  if (el) el.style.strokeDashoffset = `-${152 * (1 - pct / 100)}`;
}
function setBar(el: HTMLElement | null, pct: number) {
  if (el) el.style.width = `${pct}%`;
}

async function refreshSystemStats() {
  try {
    const r = await fetch("/api/system/stats");
    const d = await r.json();
    const cpu  = (d.cpu  as number) ?? 0;
    const mem  = (d.memory as number) ?? 0;
    const disk = (d.disk  as number) ?? 0;

    cpuValEl.textContent  = String(Math.round(cpu));
    ramValEl.textContent  = String(Math.round(mem));
    valCpuBar.textContent = `${Math.round(cpu)}%`;
    valMemEl.textContent  = d.memory_label ?? `${Math.round(mem)}%`;
    valDiskEl.textContent = d.disk_label   ?? `${Math.round(disk)}%`;

    setArcOffset(cpuArcEl, cpu);
    setArcOffset(ramArcEl, mem);
    setBar(barCpuEl,  cpu);
    setBar(barMemEl,  mem);
    setBar(barDiskEl, disk);
  } catch { /* server unreachable */ }
}
refreshSystemStats();
setInterval(refreshSystemStats, 1000);

// ---------------------------------------------------------------------------
// Agent mini-reactors
// ---------------------------------------------------------------------------

interface AgentDom {
  card:   HTMLElement | null;
  status: HTMLElement | null;
  bar:    HTMLElement | null;
  pct:    HTMLElement | null;
  usage:  SVGCircleElement | null;
  spin:   SVGCircleElement | null;
  cf:     SVGCircleElement | null;
  cr:     SVGCircleElement | null;
  glow:   SVGCircleElement | null;
  center: SVGCircleElement | null;
}

function agentDom(name: string): AgentDom {
  return {
    card:   document.getElementById(`card-${name}`),
    status: document.getElementById(`as-${name}`),
    bar:    document.getElementById(`ab-${name}`),
    pct:    document.getElementById(`ap-${name}`),
    usage:  document.getElementById(`mr-${name}-usage`)  as SVGCircleElement | null,
    spin:   document.getElementById(`mr-${name}-spin`)   as SVGCircleElement | null,
    cf:     document.getElementById(`mr-${name}-cf`)     as SVGCircleElement | null,
    cr:     document.getElementById(`mr-${name}-cr`)     as SVGCircleElement | null,
    glow:   document.getElementById(`mr-${name}-glow`)   as SVGCircleElement | null,
    center: document.getElementById(`mr-${name}-center`) as SVGCircleElement | null,
  };
}

const AGENT_NAMES = ["ultron", "echo", "friday", "vision"];
const agentDoms   = Object.fromEntries(AGENT_NAMES.map(n => [n, agentDom(n)]));

function applyAgentState(name: string, online: boolean, usage: number) {
  const d = agentDoms[name];
  if (!d) return;

  d.card?.classList.toggle("online", online);

  if (d.status) {
    d.status.textContent = online ? "● ONLINE" : "○ OFFLINE";
    d.status.className   = `agent-status-txt ${online ? "online" : "offline"}`;
  }

  if (d.bar)  d.bar.style.width = `${usage}%`;
  if (d.pct)  d.pct.textContent  = `${Math.round(usage)}%`;

  if (d.usage) d.usage.style.strokeDashoffset = String(163 * (1 - usage / 100));
  if (d.spin)  d.spin.style.opacity = online ? "0.7" : "0";

  const gIntensity = online ? (0.15 + (usage / 100) * 0.7) : 0.06;
  if (d.cf)     d.cf.setAttribute("opacity",     String(online ? 0.06 + (usage/100)*0.2 : 0.02));
  if (d.cr)     d.cr.setAttribute("opacity",     String(online ? 0.7  : 0.2));
  if (d.glow)   d.glow.setAttribute("opacity",   String(gIntensity));
  if (d.glow)   d.glow.style.filter = online
    ? `drop-shadow(0 0 ${5 + (usage/100)*8}px var(--primary-glow))`
    : "none";
  if (d.center) d.center.setAttribute("opacity", String(online ? 0.4 + (usage/100)*0.5 : 0.1));
}

async function refreshAgents() {
  try {
    const r = await fetch("/api/agents/status");
    const d = await r.json() as Record<string, { online: boolean; usage: number }>;
    for (const name of AGENT_NAMES) {
      if (d[name]) {
        // VISION is always online — only let the API update its usage %
        const online = name === 'vision' ? true : d[name].online;
        const usage  = name === 'vision' ? (d[name].usage || 40) : d[name].usage;
        applyAgentState(name, online, usage);
      }
    }
  } catch { /* server unreachable */ }
}
refreshAgents();
setInterval(refreshAgents, 5000);

// Initialise agents: offline by default, VISION always starts online
AGENT_NAMES.forEach(n => applyAgentState(n, false, 0));
applyAgentState('vision', true, 40);  // VISION is always active

// Boot animation — stagger each reactor core on page load
AGENT_NAMES.forEach((name, i) => {
  setTimeout(() => {
    const card = document.getElementById(`card-${name}`);
    if (!card) return;
    card.classList.add("booting");
    // Remove class after animation completes so it can re-trigger
    card.addEventListener("animationend", () => card.classList.remove("booting"), { once: true });
  }, 600 + i * 320);
});

// ---------------------------------------------------------------------------
// Icon strip — sidebar + drawers
// ---------------------------------------------------------------------------

const drawerLaunch    = document.getElementById("drawer-launch")!;
const drawerTelemetry = document.getElementById("drawer-telemetry")!;
const btnStripLaunch    = document.getElementById("btn-strip-launch")!;
const btnStripTelemetry = document.getElementById("btn-strip-telemetry")!;

function closeAllDrawers() {
  [drawerLaunch, drawerTelemetry].forEach(d => d.classList.remove("open"));
  [btnStripLaunch, btnStripTelemetry].forEach(b => b.classList.remove("active"));
}

function toggleDrawer(drawer: HTMLElement, btn: HTMLButtonElement | HTMLElement) {
  const isOpen = drawer.classList.contains("open");
  closeAllDrawers();
  if (!isOpen) {
    drawer.classList.add("open");
    btn.classList.add("active");
  }
}

btnStripLaunch.addEventListener("click", (e) => {
  e.stopPropagation();
  toggleDrawer(drawerLaunch, btnStripLaunch);
});

btnStripTelemetry.addEventListener("click", (e) => {
  e.stopPropagation();
  toggleDrawer(drawerTelemetry, btnStripTelemetry);
});

// Close right-side drawers when clicking outside
document.addEventListener("click", (e) => {
  const target = e.target as Node;
  const insideDrawer = [drawerLaunch, drawerTelemetry].some(d => d.contains(target));
  const insideBtn    = [btnStripLaunch, btnStripTelemetry].some(b => b.contains(target));
  if (!insideDrawer && !insideBtn) closeAllDrawers();
});

// Quick launch hex buttons
document.querySelectorAll<HTMLButtonElement>(".hex-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    const cmd = btn.dataset.cmd;
    if (!cmd) return;
    closeAllDrawers();
    audioPlayer.stop();
    socket.send({ type: "transcript", text: cmd, isFinal: true });
    transition("thinking");
  });
});

// First-time setup check
setTimeout(() => { checkFirstTimeSetup(); }, 2000);

// ---------------------------------------------------------------------------
// Language pill — instant language switching
// ---------------------------------------------------------------------------

const LANG_LABELS: Record<string, string> = {
  "en-US": "EN",  "hi-IN": "हिं", "ta-IN": "த",
  "te-IN": "తె",  "ml-IN": "മ",   "kn-IN": "ಕ",  "sv-SE": "SV",
};

const langPillEl  = document.getElementById("lang-pill")!;
const langLabelEl = document.getElementById("lang-pill-label")!;
const langFlyout  = document.getElementById("lang-flyout")!;

function setActiveLangOption(langCode: string) {
  document.querySelectorAll<HTMLButtonElement>(".lang-opt").forEach(btn => {
    btn.classList.toggle("active", btn.dataset.lang === langCode);
  });
  langLabelEl.textContent = LANG_LABELS[langCode] ?? langCode.split("-")[0].toUpperCase();
}

// Initialise pill to stored language
setActiveLangOption(localStorage.getItem("jarvis-lang") || "en-US");

langPillEl.addEventListener("click", (e) => {
  e.stopPropagation();
  langFlyout.classList.toggle("open");
});

document.querySelectorAll<HTMLButtonElement>(".lang-opt").forEach(btn => {
  btn.addEventListener("click", (e) => {
    e.stopPropagation();
    const lang = btn.dataset.lang!;
    voiceInput.setLang(lang);
    setActiveLangOption(lang);
    langFlyout.classList.remove("open");
  });
});

// Close flyout on outside click
document.addEventListener("click", (e) => {
  if (!langFlyout.contains(e.target as Node) && !langPillEl.contains(e.target as Node)) {
    langFlyout.classList.remove("open");
  }
});

// Expose for settings panel
(window as any).setJarvisLang = (lang: string) => {
  voiceInput.setLang(lang);
  setActiveLangOption(lang);
};
