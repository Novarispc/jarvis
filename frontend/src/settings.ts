/**
 * JARVIS — Settings Panel
 */

interface StatusResponse {
  claude_code_installed: boolean;
  memory_count: number;
  task_count: number;
  server_port: number;
  uptime_seconds: number;
}

interface PreferencesResponse {
  user_name: string;
  honorific: string;
  orb_color?: string;
}

let panelEl: HTMLElement | null = null;
let isOpen = false;

async function apiGet<T>(url: string): Promise<T> {
  const res = await fetch(url);
  return res.json();
}

async function apiPost<T>(url: string, body: unknown): Promise<T> {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return res.json();
}

function formatUptime(seconds: number): string {
  if (seconds < 60) return `${Math.floor(seconds)}s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m`;
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  return `${h}h ${m}m`;
}

function buildPanelHTML(): string {
  return `
    <div class="settings-backdrop" id="settings-backdrop"></div>
    <div class="settings-panel" id="settings-panel-inner">

      <div class="settings-header">
        <div class="settings-title">S Y S T E M &nbsp; C O N F I G</div>
        <button class="settings-close-btn" id="settings-close">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
          </svg>
        </button>
      </div>

      <div class="settings-body">

        <!-- Connection Status -->
        <div class="hud-panel settings-section-panel" id="section-status">
          <div class="hud-panel-hdr">
            <span class="panel-dot-pulse"></span>
            <span class="panel-label">Connection Status</span>
          </div>
          <div class="status-grid">
            <div class="status-row">
              <span class="status-dot" id="status-claude-cli"></span>
              <span>Claude Code CLI</span>
            </div>
            <div class="status-row">
              <span class="status-dot" id="status-server"></span>
              <span>Server</span>
              <span class="status-detail" id="status-server-detail"></span>
            </div>
          </div>
        </div>

        <!-- System Diagnostics -->
        <div class="hud-panel settings-section-panel" id="section-diagnostics">
          <div class="hud-panel-hdr">
            <span class="panel-dot-pulse"></span>
            <span class="panel-label">System Diagnostics</span>
          </div>
          <div class="sysinfo-grid">
            <div class="sysinfo-row">
              <span class="sysinfo-label">Uptime</span>
              <span id="diag-uptime">--</span>
            </div>
            <div class="sysinfo-row">
              <span class="sysinfo-label">Core Temp</span>
              <span>54°C</span>
            </div>
            <div class="sysinfo-row">
              <span class="sysinfo-label">Network</span>
              <span id="diag-network">OPTIMAL</span>
            </div>
            <div class="sysinfo-row">
              <span class="sysinfo-label">Protocol</span>
              <span>v0.1.0</span>
            </div>
            <div class="sysinfo-row">
              <span class="sysinfo-label">Memory Entries</span>
              <span id="sysinfo-memory">--</span>
            </div>
            <div class="sysinfo-row">
              <span class="sysinfo-label">Tasks</span>
              <span id="sysinfo-tasks">--</span>
            </div>
            <div class="sysinfo-row">
              <span class="sysinfo-label">Server Port</span>
              <span id="sysinfo-port">--</span>
            </div>
          </div>
        </div>

        <!-- User Preferences -->
        <div class="hud-panel settings-section-panel" id="section-preferences">
          <div class="hud-panel-hdr">
            <span class="panel-dot-pulse"></span>
            <span class="panel-label">User Preferences</span>
          </div>
          <div class="settings-field">
            <label>Your Name</label>
            <input type="text" id="input-user-name" placeholder="Enter name" />
          </div>
          <div class="settings-field">
            <label>Honorific</label>
            <select id="input-honorific">
              <option value="sir">Sir</option>
              <option value="ma'am">Ma'am</option>
              <option value="none">None</option>
            </select>
          </div>
          <div class="settings-actions">
            <button class="settings-btn primary" id="btn-save-prefs">Save</button>
          </div>
        </div>

        <!-- Voice Options -->
        <div class="hud-panel settings-section-panel" id="section-voice">
          <div class="hud-panel-hdr">
            <span class="panel-dot-pulse"></span>
            <span class="panel-label">Voice Options</span>
          </div>
          <div class="settings-field">
            <label>TTS Voice</label>
            <div class="settings-input-row">
              <select id="input-tts-voice">
                <option value="en-GB-RyanNeural">British Male (Default)</option>
                <option value="en-US-AriaNeural">American Female</option>
                <option value="en-AU-NatashaNeural">Australian Female</option>
                <option value="en-IN-NeerjaNeural">Indian Female</option>
              </select>
              <button class="settings-btn" id="btn-preview-voice">Test</button>
            </div>
          </div>
          <div class="settings-actions">
            <button class="settings-btn primary" id="btn-save-voice">Save</button>
          </div>
        </div>

        <!-- Language -->
        <div class="hud-panel settings-section-panel" id="section-language">
          <div class="hud-panel-hdr">
            <span class="panel-dot-pulse"></span>
            <span class="panel-label">Language</span>
          </div>
          <div class="settings-field">
            <label>Recognition &amp; Response Language</label>
            <select id="input-lang">
              <option value="en-US">English (Default)</option>
              <option value="hi-IN">Hindi — हिन्दी</option>
              <option value="ta-IN">Tamil — தமிழ்</option>
              <option value="te-IN">Telugu — తెలుగు</option>
              <option value="ml-IN">Malayalam — മലയാളം</option>
              <option value="kn-IN">Kannada — ಕನ್ನಡ</option>
              <option value="sv-SE">Swedish — Svenska</option>
            </select>
          </div>
          <div class="settings-actions">
            <button class="settings-btn primary" id="btn-save-lang">Apply Language</button>
          </div>
        </div>

        <!-- Orb Color -->
        <div class="hud-panel settings-section-panel" id="section-color">
          <div class="hud-panel-hdr">
            <span class="panel-dot-pulse"></span>
            <span class="panel-label">Orb Color</span>
          </div>
          <div class="settings-field">
            <label>Presets</label>
            <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-top:6px;">
              <button class="color-swatch" id="color-cyan"   style="background:#00d4ff;" title="Cyan"></button>
              <button class="color-swatch" id="color-blue"   style="background:#4ca8e8;" title="Blue"></button>
              <button class="color-swatch" id="color-purple" style="background:#a855f7;" title="Purple"></button>
              <button class="color-swatch" id="color-pink"   style="background:#ec4899;" title="Pink"></button>
              <button class="color-swatch" id="color-green"  style="background:#10b981;" title="Green"></button>
              <button class="color-swatch" id="color-orange" style="background:#f97316;" title="Orange"></button>
              <button class="color-swatch" id="color-red"    style="background:#ef4444;" title="Red"></button>
              <button class="color-swatch" id="color-yellow" style="background:#eab308;" title="Yellow"></button>
            </div>
          </div>
          <div class="settings-field">
            <label>Custom Hex</label>
            <div class="settings-input-row">
              <input type="text" id="input-hex-color" placeholder="#00d4ff" maxlength="7" />
              <div id="hex-preview" style="background:#00d4ff;"></div>
            </div>
          </div>
          <div class="settings-actions">
            <button class="settings-btn primary" id="btn-save-color">Save Color</button>
          </div>
        </div>

        <!-- Status Text Color -->
        <div class="hud-panel settings-section-panel" id="section-text-color">
          <div class="hud-panel-hdr">
            <span class="panel-dot-pulse"></span>
            <span class="panel-label">Status Text Color</span>
          </div>
          <div class="settings-field">
            <label>Presets</label>
            <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-top:6px;">
              <button class="color-swatch tc-swatch" id="tc-cyan"   style="background:#00d4ff;" title="Cyan"></button>
              <button class="color-swatch tc-swatch" id="tc-white"  style="background:#d6f3ff;" title="White"></button>
              <button class="color-swatch tc-swatch" id="tc-purple" style="background:#a855f7;" title="Purple"></button>
              <button class="color-swatch tc-swatch" id="tc-pink"   style="background:#ec4899;" title="Pink"></button>
              <button class="color-swatch tc-swatch" id="tc-green"  style="background:#10b981;" title="Green"></button>
              <button class="color-swatch tc-swatch" id="tc-orange" style="background:#f97316;" title="Orange"></button>
              <button class="color-swatch tc-swatch" id="tc-red"    style="background:#ef4444;" title="Red"></button>
              <button class="color-swatch tc-swatch" id="tc-yellow" style="background:#eab308;" title="Yellow"></button>
            </div>
          </div>
          <div class="settings-field">
            <label>Custom Hex</label>
            <div class="settings-input-row">
              <input type="text" id="input-tc-hex" placeholder="#00d4ff" maxlength="7" />
              <div id="tc-hex-preview" style="background:#00d4ff;"></div>
            </div>
          </div>
          <div class="settings-actions">
            <button class="settings-btn primary" id="btn-save-tc">Save Color</button>
          </div>
        </div>

        <!-- Actions -->
        <div class="hud-panel settings-section-panel" id="section-actions">
          <div class="hud-panel-hdr">
            <span class="panel-dot-pulse"></span>
            <span class="panel-label">Actions</span>
          </div>
          <div style="display:flex;flex-direction:column;gap:8px;">
            <button class="settings-btn danger" id="btn-restart">Restart Server</button>
            <button class="settings-btn danger" id="btn-fix-self">Fix Yourself (Work Mode)</button>
          </div>
        </div>

      </div>
    </div>
  `;
}

function createPanel(): HTMLElement {
  const container = document.createElement("div");
  container.id = "settings-container";
  container.innerHTML = buildPanelHTML();
  document.body.appendChild(container);
  return container;
}

function setDotStatus(id: string, status: "green" | "red" | "yellow" | "off") {
  const dot = document.getElementById(id);
  if (!dot) return;
  dot.className = "status-dot";
  if (status !== "off") dot.classList.add(`status-${status}`);
}

async function loadStatus() {
  try {
    const status = await apiGet<StatusResponse>("/api/settings/status");

    setDotStatus("status-claude-cli", status.claude_code_installed ? "green" : "red");
    setDotStatus("status-server", "green");

    const serverDetail = document.getElementById("status-server-detail");
    if (serverDetail) serverDetail.textContent = `port ${status.server_port}`;

    // Diagnostics
    const secs = status.uptime_seconds || 0;
    const days = Math.floor(secs / 86400);
    const hrs  = Math.floor((secs % 86400) / 3600);
    const mins = Math.floor((secs % 3600) / 60);
    const uptimeEl = document.getElementById("diag-uptime");
    if (uptimeEl) uptimeEl.textContent = `${days}D ${hrs}H ${mins}M`;

    const netEl = document.getElementById("diag-network");
    if (netEl) netEl.textContent = "OPTIMAL";

    // System info
    const memEl  = document.getElementById("sysinfo-memory");
    const taskEl = document.getElementById("sysinfo-tasks");
    const portEl = document.getElementById("sysinfo-port");
    if (memEl)  memEl.textContent  = String(status.memory_count);
    if (taskEl) taskEl.textContent = String(status.task_count);
    if (portEl) portEl.textContent = String(status.server_port);

    return status;
  } catch {
    setDotStatus("status-server", "red");
    const netEl = document.getElementById("diag-network");
    if (netEl) netEl.textContent = "OFFLINE";
    return null;
  }
}

async function loadPreferences() {
  try {
    const prefs = await apiGet<PreferencesResponse>("/api/settings/preferences");
    const nameEl = document.getElementById("input-user-name") as HTMLInputElement;
    const honEl  = document.getElementById("input-honorific") as HTMLSelectElement;
    if (nameEl) nameEl.value = prefs.user_name || "";
    if (honEl)  honEl.value  = prefs.honorific || "sir";

    if (prefs.orb_color) {
      localStorage.setItem("jarvis-orb-color", prefs.orb_color);
      if (typeof (window as any).setOrbColor === "function") {
        (window as any).setOrbColor(prefs.orb_color);
      }
    }
  } catch { /* ignore */ }
}

async function synthesizeSpeech(text: string): Promise<string | null> {
  try {
    const res = await fetch("/api/synthesize", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    });
    const data = await res.json();
    return data.audio || null;
  } catch { return null; }
}

function base64ToArrayBuffer(base64: string): ArrayBuffer {
  const binary = atob(base64);
  const bytes  = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
  return bytes.buffer;
}

function wireEvents() {
  document.getElementById("settings-close")?.addEventListener("click", closeSettings);
  document.getElementById("settings-backdrop")?.addEventListener("click", closeSettings);

  // Color swatches
  const colorMap: Record<string, string> = {
    "color-cyan":   "#00d4ff",
    "color-blue":   "#4ca8e8",
    "color-purple": "#a855f7",
    "color-pink":   "#ec4899",
    "color-green":  "#10b981",
    "color-orange": "#f97316",
    "color-red":    "#ef4444",
    "color-yellow": "#eab308",
  };

  function applyColor(color: string) {
    if (typeof (window as any).setOrbColor === "function") {
      (window as any).setOrbColor(color);
    }
    localStorage.setItem("jarvis-orb-color", color);
    const user_name = (document.getElementById("input-user-name") as HTMLInputElement)?.value.trim() || "";
    const honorific = (document.getElementById("input-honorific") as HTMLSelectElement)?.value || "sir";
    apiPost("/api/settings/preferences", { user_name, honorific, orb_color: color }).catch(() => {});
  }

  Object.entries(colorMap).forEach(([id, color]) => {
    document.getElementById(id)?.addEventListener("click", () => {
      applyColor(color);
      document.querySelectorAll(".color-swatch").forEach(b => b.classList.remove("color-selected"));
      document.getElementById(id)?.classList.add("color-selected");
      const hexInput   = document.getElementById("input-hex-color") as HTMLInputElement;
      const hexPreview = document.getElementById("hex-preview") as HTMLElement;
      if (hexInput)   hexInput.value = color;
      if (hexPreview) hexPreview.style.background = color;
    });
  });

  // Restore saved color swatch selection
  const savedColor = localStorage.getItem("jarvis-orb-color") || "#00d4ff";
  for (const [id, color] of Object.entries(colorMap)) {
    if (color === savedColor) document.getElementById(id)?.classList.add("color-selected");
  }
  const hexInputEl = document.getElementById("input-hex-color") as HTMLInputElement;
  if (hexInputEl) hexInputEl.value = savedColor;
  const hexPreviewEl = document.getElementById("hex-preview") as HTMLElement;
  if (hexPreviewEl) hexPreviewEl.style.background = savedColor;

  // Save preferences
  document.getElementById("btn-save-prefs")?.addEventListener("click", async () => {
    const user_name = (document.getElementById("input-user-name") as HTMLInputElement).value.trim();
    const honorific = (document.getElementById("input-honorific") as HTMLSelectElement).value;
    const orb_color = localStorage.getItem("jarvis-orb-color") || "#00d4ff";
    await apiPost("/api/settings/preferences", { user_name, honorific, orb_color });
    await loadStatus();
  });

  // Voice preview
  document.getElementById("btn-preview-voice")?.addEventListener("click", async () => {
    const voice = (document.getElementById("input-tts-voice") as HTMLSelectElement)?.value || "en-GB-RyanNeural";
    const audio = await synthesizeSpeech(`Testing ${voice.split('-')[1]} voice.`);
    if (audio) {
      const audioData = base64ToArrayBuffer(audio);
      const ctx = new (window as any).AudioContext();
      const src = ctx.createBufferSource();
      src.buffer = await ctx.decodeAudioData(audioData);
      src.connect(ctx.destination);
      src.start(0);
    }
  });

  // Voice save
  document.getElementById("btn-save-voice")?.addEventListener("click", async () => {
    const voice = (document.getElementById("input-tts-voice") as HTMLSelectElement)?.value || "en-GB-RyanNeural";
    await apiPost("/api/settings/keys", { key_name: "EDGE_TTS_VOICE", key_value: voice });
  });

  // Hex color input
  document.getElementById("input-hex-color")?.addEventListener("input", (e) => {
    const value = (e.target as HTMLInputElement).value.trim();
    if (/^#[0-9A-F]{6}$/i.test(value)) {
      const preview = document.getElementById("hex-preview") as HTMLElement;
      if (preview) preview.style.background = value;
      document.querySelectorAll(".color-swatch").forEach(b => b.classList.remove("color-selected"));
      applyColor(value);
    }
  });

  // Save color button
  document.getElementById("btn-save-color")?.addEventListener("click", async () => {
    const color = localStorage.getItem("jarvis-orb-color") || "#00d4ff";
    const user_name = (document.getElementById("input-user-name") as HTMLInputElement)?.value.trim() || "";
    const honorific = (document.getElementById("input-honorific") as HTMLSelectElement)?.value || "sir";
    await apiPost("/api/settings/preferences", { user_name, honorific, orb_color: color });
  });

  // Status text color swatches
  const tcColorMap: Record<string, string> = {
    "tc-cyan":   "#00d4ff",
    "tc-white":  "#d6f3ff",
    "tc-purple": "#a855f7",
    "tc-pink":   "#ec4899",
    "tc-green":  "#10b981",
    "tc-orange": "#f97316",
    "tc-red":    "#ef4444",
    "tc-yellow": "#eab308",
  };

  function applyTextColor(color: string) {
    if (typeof (window as any).setOrbTextColor === "function") {
      (window as any).setOrbTextColor(color);
    }
    localStorage.setItem("jarvis-orb-text-color", color);
  }

  Object.entries(tcColorMap).forEach(([id, color]) => {
    document.getElementById(id)?.addEventListener("click", () => {
      applyTextColor(color);
      document.querySelectorAll(".tc-swatch").forEach(b => b.classList.remove("color-selected"));
      document.getElementById(id)?.classList.add("color-selected");
      const inp = document.getElementById("input-tc-hex") as HTMLInputElement;
      const prv = document.getElementById("tc-hex-preview") as HTMLElement;
      if (inp) inp.value = color;
      if (prv) prv.style.background = color;
    });
  });

  // Restore saved text color swatch
  const savedTcColor = localStorage.getItem("jarvis-orb-text-color") || "#00d4ff";
  for (const [id, color] of Object.entries(tcColorMap)) {
    if (color === savedTcColor) document.getElementById(id)?.classList.add("color-selected");
  }
  const tcHexInputEl = document.getElementById("input-tc-hex") as HTMLInputElement;
  if (tcHexInputEl) tcHexInputEl.value = savedTcColor;
  const tcHexPreviewEl = document.getElementById("tc-hex-preview") as HTMLElement;
  if (tcHexPreviewEl) tcHexPreviewEl.style.background = savedTcColor;

  document.getElementById("input-tc-hex")?.addEventListener("input", (e) => {
    const value = (e.target as HTMLInputElement).value.trim();
    if (/^#[0-9A-F]{6}$/i.test(value)) {
      const prv = document.getElementById("tc-hex-preview") as HTMLElement;
      if (prv) prv.style.background = value;
      document.querySelectorAll(".tc-swatch").forEach(b => b.classList.remove("color-selected"));
      applyTextColor(value);
    }
  });

  document.getElementById("btn-save-tc")?.addEventListener("click", () => {
    const color = localStorage.getItem("jarvis-orb-text-color") || "#00d4ff";
    applyTextColor(color);
  });

  // Language selector — restore saved value
  const langSelect = document.getElementById("input-lang") as HTMLSelectElement;
  if (langSelect) {
    langSelect.value = localStorage.getItem("jarvis-lang") || "en-US";
  }

  // Apply language — instant switch via global helper (no page reload needed)
  document.getElementById("btn-save-lang")?.addEventListener("click", () => {
    const lang = langSelect?.value || "en-US";
    if (typeof (window as any).setJarvisLang === "function") {
      (window as any).setJarvisLang(lang);
    } else {
      localStorage.setItem("jarvis-lang", lang);
      window.location.reload();
    }
    closeSettings();
  });

  // Restart server
  document.getElementById("btn-restart")?.addEventListener("click", async () => {
    const btn = document.getElementById("btn-restart") as HTMLButtonElement;
    if (btn) btn.textContent = "Restarting...";
    try {
      await fetch("/api/restart", { method: "POST" });
      setTimeout(() => window.location.reload(), 4000);
    } catch {
      if (btn) btn.textContent = "Restart Failed";
    }
  });

  // Fix self (work mode)
  document.getElementById("btn-fix-self")?.addEventListener("click", () => {
    // Broadcast to the active WebSocket — find it via window
    const sendFn = (window as any).__jarvisSend;
    if (typeof sendFn === "function") sendFn({ type: "fix_self" });
    closeSettings();
  });
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

export async function openSettings() {
  if (isOpen) return;
  isOpen = true;

  if (!panelEl) {
    panelEl = createPanel();
    wireEvents();
  }

  panelEl.style.display = "block";
  requestAnimationFrame(() => { panelEl!.classList.add("open"); });

  await loadStatus();
  await loadPreferences();
}

export function closeSettings() {
  if (!panelEl || !isOpen) return;
  isOpen = false;
  panelEl.classList.remove("open");
  setTimeout(() => { if (panelEl) panelEl.style.display = "none"; }, 300);
}

export function isSettingsOpen(): boolean { return isOpen; }

export async function checkFirstTimeSetup(): Promise<boolean> { return false; }
