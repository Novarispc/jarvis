/**
 * JARVIS — Settings Panel
 *
 * Overlay panel for API keys, connection status, preferences, and system info.
 * Slides in from the right with glass-morphism styling.
 */

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

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

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------

let panelEl: HTMLElement | null = null;
let isOpen = false;

// ---------------------------------------------------------------------------
// API helpers
// ---------------------------------------------------------------------------

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

// ---------------------------------------------------------------------------
// Panel HTML
// ---------------------------------------------------------------------------

function buildPanelHTML(): string {
  return `
    <div class="settings-backdrop" id="settings-backdrop"></div>
    <div class="settings-panel" id="settings-panel-inner">
      <div class="settings-header">
        <h2>Settings</h2>
        <button class="settings-close" id="settings-close">&times;</button>
      </div>

      <div class="settings-body">

        <!-- Connection Status -->
        <section class="settings-section" id="section-status">
          <h3>Connection Status</h3>
          <div class="status-grid">
            <div class="status-row"><span class="status-dot" id="status-claude-cli"></span><span>Claude Code CLI</span></div>
            <div class="status-row"><span class="status-dot" id="status-server"></span><span>Server</span><span class="status-detail" id="status-server-detail"></span></div>
          </div>
        </section>

        <!-- User Preferences -->
        <section class="settings-section" id="section-preferences">
          <h3>User Preferences</h3>

          <div class="settings-field">
            <label>Your Name</label>
            <input type="text" id="input-user-name" placeholder="Your name" />
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
            <button class="settings-btn primary" id="btn-save-prefs">Save Preferences</button>
          </div>
        </section>

        <!-- Voice Options -->
        <section class="settings-section" id="section-voice">
          <h3>Voice Options</h3>

          <div class="settings-field">
            <label>TTS Voice</label>
            <div class="settings-input-row">
              <select id="input-tts-voice">
                <option value="en-GB-RyanNeural">British Male (Default)</option>
                <option value="en-US-AriaNeural">American Female</option>
                <option value="en-AU-NatashaNeural">Australian Female</option>
                <option value="en-IN-NeerjaNeural">Indian Female</option>
              </select>
              <button class="settings-btn" id="btn-preview-voice">Preview</button>
            </div>
          </div>

          <div class="settings-actions">
            <button class="settings-btn primary" id="btn-save-voice">Save Voice</button>
          </div>
        </section>

        <!-- Color Customization -->
        <section class="settings-section" id="section-color">
          <h3>Orb Color</h3>

          <div class="settings-field">
            <label>Preset Colors</label>
            <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; margin-top: 8px;">
              <button class="color-swatch" id="color-blue" style="background: #4ca8e8;" title="Blue (default)"></button>
              <button class="color-swatch" id="color-cyan" style="background: #00d9ff;" title="Cyan"></button>
              <button class="color-swatch" id="color-purple" style="background: #a855f7;" title="Purple"></button>
              <button class="color-swatch" id="color-pink" style="background: #ec4899;" title="Pink"></button>
              <button class="color-swatch" id="color-green" style="background: #10b981;" title="Green"></button>
              <button class="color-swatch" id="color-orange" style="background: #f97316;" title="Orange"></button>
              <button class="color-swatch" id="color-red" style="background: #ef4444;" title="Red"></button>
              <button class="color-swatch" id="color-yellow" style="background: #eab308;" title="Yellow"></button>
            </div>
          </div>

          <div class="settings-field">
            <label>Custom Hex Color</label>
            <div class="settings-input-row">
              <input type="text" id="input-hex-color" placeholder="#4ca8e8" maxlength="7" />
              <span id="hex-preview" style="width: 30px; height: 30px; background: #4ca8e8; border-radius: 4px; border: 1px solid #666;"></span>
            </div>
          </div>

          <div class="settings-actions">
            <button class="settings-btn primary" id="btn-save-color">Save Color</button>
          </div>
        </section>

        <!-- System Info -->
        <section class="settings-section" id="section-sysinfo">
          <h3>System Info</h3>
          <div class="sysinfo-grid">
            <div class="sysinfo-row"><span class="sysinfo-label">Memory entries</span><span id="sysinfo-memory">--</span></div>
            <div class="sysinfo-row"><span class="sysinfo-label">Tasks</span><span id="sysinfo-tasks">--</span></div>
            <div class="sysinfo-row"><span class="sysinfo-label">Server port</span><span id="sysinfo-port">--</span></div>
            <div class="sysinfo-row"><span class="sysinfo-label">Uptime</span><span id="sysinfo-uptime">--</span></div>
          </div>
        </section>

      </div>
    </div>
  `;
}

// ---------------------------------------------------------------------------
// Panel lifecycle
// ---------------------------------------------------------------------------

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

function formatUptime(seconds: number): string {
  if (seconds < 60) return `${Math.floor(seconds)}s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m`;
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  return `${h}h ${m}m`;
}


async function loadStatus() {
  try {
    const status = await apiGet<StatusResponse>("/api/settings/status");

    setDotStatus("status-claude-cli", status.claude_code_installed ? "green" : "red");
    setDotStatus("status-server", "green");

    const serverDetail = document.getElementById("status-server-detail");
    if (serverDetail) serverDetail.textContent = `port ${status.server_port} | up ${formatUptime(status.uptime_seconds)}`;

    // System info
    const memEl = document.getElementById("sysinfo-memory");
    if (memEl) memEl.textContent = String(status.memory_count);
    const taskEl = document.getElementById("sysinfo-tasks");
    if (taskEl) taskEl.textContent = String(status.task_count);
    const portEl = document.getElementById("sysinfo-port");
    if (portEl) portEl.textContent = String(status.server_port);
    const upEl = document.getElementById("sysinfo-uptime");
    if (upEl) upEl.textContent = formatUptime(status.uptime_seconds);

    return status;
  } catch (e) {
    console.error("[settings] failed to load status:", e);
    setDotStatus("status-server", "red");
    return null;
  }
}

async function loadPreferences() {
  try {
    const prefs = await apiGet<PreferencesResponse>("/api/settings/preferences");
    const nameEl = document.getElementById("input-user-name") as HTMLInputElement;
    const honEl = document.getElementById("input-honorific") as HTMLSelectElement;
    if (nameEl) nameEl.value = prefs.user_name || "";
    if (honEl) honEl.value = prefs.honorific || "sir";

    // Restore saved color — update CSS variable AND live Three.js orb
    if (prefs.orb_color) {
      localStorage.setItem("jarvis-orb-color", prefs.orb_color);
      document.documentElement.style.setProperty("--orb-color", prefs.orb_color);
      if (typeof (window as any).setOrbColor === "function") {
        (window as any).setOrbColor(prefs.orb_color);
      }
    }
  } catch (e) {
    console.error("[settings] failed to load preferences:", e);
  }
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
  } catch (e) {
    console.error("[settings] TTS synthesis failed:", e);
    return null;
  }
}

function base64ToArrayBuffer(base64: string): ArrayBuffer {
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) {
    bytes[i] = binary.charCodeAt(i);
  }
  return bytes.buffer;
}

function wireEvents() {
  // Close
  document.getElementById("settings-close")?.addEventListener("click", closeSettings);
  document.getElementById("settings-backdrop")?.addEventListener("click", closeSettings);

  // Color swatches
  const colorMap: Record<string, string> = {
    "color-blue": "#4ca8e8",
    "color-cyan": "#00d9ff",
    "color-purple": "#a855f7",
    "color-pink": "#ec4899",
    "color-green": "#10b981",
    "color-orange": "#f97316",
    "color-red": "#ef4444",
    "color-yellow": "#eab308",
  };

  function applyColor(color: string) {
    // Update CSS variable
    document.documentElement.style.setProperty("--orb-color", color);
    // Update Three.js orb immediately
    if (typeof (window as any).setOrbColor === "function") {
      (window as any).setOrbColor(color);
    }
    // Persist locally
    localStorage.setItem("jarvis-orb-color", color);
    // Persist to backend (fire and forget)
    const orb_color = color;
    const user_name = (document.getElementById("input-user-name") as HTMLInputElement)?.value.trim() || "";
    const honorific = (document.getElementById("input-honorific") as HTMLSelectElement)?.value || "sir";
    apiPost("/api/settings/preferences", { user_name, honorific, orb_color }).catch(() => {});
  }

  Object.entries(colorMap).forEach(([id, color]) => {
    document.getElementById(id)?.addEventListener("click", () => {
      applyColor(color);
      // Visual feedback
      document.querySelectorAll(".color-swatch").forEach(btn => btn.classList.remove("color-selected"));
      (document.getElementById(id) as HTMLElement)?.classList.add("color-selected");
      // Sync hex input
      const hexInput = document.getElementById("input-hex-color") as HTMLInputElement;
      const hexPreview = document.getElementById("hex-preview") as HTMLElement;
      if (hexInput) hexInput.value = color;
      if (hexPreview) hexPreview.style.background = color;
    });
  });

  // Load saved color on init
  const savedColor = localStorage.getItem("jarvis-orb-color") || "#4ca8e8";
  document.documentElement.style.setProperty("--orb-color", savedColor);
  for (const [id, color] of Object.entries(colorMap)) {
    if (color === savedColor) {
      (document.getElementById(id) as HTMLElement)?.classList.add("color-selected");
    }
  }

  // Save preferences
  document.getElementById("btn-save-prefs")?.addEventListener("click", async () => {
    const user_name = (document.getElementById("input-user-name") as HTMLInputElement).value.trim();
    const honorific = (document.getElementById("input-honorific") as HTMLSelectElement).value;
    const orb_color = localStorage.getItem("jarvis-orb-color") || "#4ca8e8";
    await apiPost("/api/settings/preferences", { user_name, honorific, orb_color });
    await loadStatus();
  });

  // Voice preview
  document.getElementById("btn-preview-voice")?.addEventListener("click", async () => {
    const voiceSelect = document.getElementById("input-tts-voice") as HTMLSelectElement;
    const voice = voiceSelect?.value || "en-GB-RyanNeural";
    try {
      const audio = await synthesizeSpeech(`Testing voice with ${voice.split('-')[1]} accent.`);
      if (audio) {
        const audioData = base64ToArrayBuffer(audio);
        const audioContext = new (window as any).AudioContext();
        const source = audioContext.createBufferSource();
        const decoded = await audioContext.decodeAudioData(audioData);
        source.buffer = decoded;
        source.connect(audioContext.destination);
        source.start(0);
      }
    } catch (e) {
      console.error("[settings] Voice preview failed:", e);
    }
  });

  // Voice save
  document.getElementById("btn-save-voice")?.addEventListener("click", async () => {
    const voiceSelect = document.getElementById("input-tts-voice") as HTMLSelectElement;
    const voice = voiceSelect?.value || "en-GB-RyanNeural";
    await apiPost("/api/settings/keys", { key_name: "EDGE_TTS_VOICE", key_value: voice });
    console.log("[settings] Saved voice:", voice);
  });

  // Hex color input — applies instantly on valid input
  const hexInput = document.getElementById("input-hex-color") as HTMLInputElement;
  const hexPreview = document.getElementById("hex-preview") as HTMLElement;
  hexInput?.addEventListener("input", (e) => {
    const value = (e.target as HTMLInputElement).value.trim();
    if (/^#[0-9A-F]{6}$/i.test(value)) {
      if (hexPreview) hexPreview.style.background = value;
      // Clear swatch selection since this is a custom color
      document.querySelectorAll(".color-swatch").forEach(btn => btn.classList.remove("color-selected"));
      applyColor(value);
    }
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

  // Trigger animation
  requestAnimationFrame(() => {
    panelEl!.classList.add("open");
  });

  // Load data
  const status = await loadStatus();
  await loadPreferences();

}

export function closeSettings() {
  if (!panelEl || !isOpen) return;
  isOpen = false;
  panelEl.classList.remove("open");
  setTimeout(() => {
    if (panelEl) panelEl.style.display = "none";
  }, 300);
}

export function isSettingsOpen(): boolean {
  return isOpen;
}

/**
 * Check if first-time setup is needed and auto-open.
 */
export async function checkFirstTimeSetup(): Promise<boolean> {
  return false;
}
