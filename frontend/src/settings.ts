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
  calendar_accessible: boolean;
  mail_accessible: boolean;
  notes_accessible: boolean;
  memory_count: number;
  task_count: number;
  server_port: number;
  uptime_seconds: number;
  env_keys_set: {
    anthropic: boolean;
  };
}

interface PreferencesResponse {
  user_name: string;
  honorific: string;
  calendar_accounts: string;
  orb_color?: string;
}

interface Agent {
  id: string;
  name: string;
  role: string;
  description: string;
  enabled: boolean;
  apiKeyField?: string;
}

interface FutureAgent {
  name: string;
  role: string;
  description: string;
}

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------

let panelEl: HTMLElement | null = null;
let isOpen = false;
let isFirstTimeSetup = false;
let setupStep = 0; // 0=anthropic, 1=fish, 2=name, 3=done

// Agent configuration
const AGENTS: Agent[] = [
  { id: "jarvis", name: "JARVIS", role: "Multi-Agent Supervisor", description: "Master orchestrator and voice interface", enabled: true },
  { id: "friday", name: "FRIDAY", role: "Task Planner", description: "Database organization and scheduling", enabled: false },
  { id: "vision", name: "VISION", role: "Learning & Skill Forge", description: "Memory and skill accumulation", enabled: false },
  { id: "edith", name: "EDITH", role: "Memory & Context", description: "Documentation and persistent facts", enabled: false },
  { id: "echo", name: "ECHO", role: "Social Media Manager", description: "Content mirroring and listening", enabled: false },
  { id: "nova", name: "NOVA", role: "PC Launcher", description: "Application and dependency management", enabled: false },
  { id: "hulk", name: "HULK", role: "Task Completion Reporter", description: "Testing and error handling", enabled: false },
  { id: "ultron", name: "ULTRON", role: "Frontend & Backend", description: "UI rendering and logic engine", enabled: false },
  { id: "thor", name: "THOR", role: "Code Review", description: "Code critique and quality gates", enabled: false },
  { id: "shield", name: "S.H.I.E.L.D.", role: "Network & API Gateway", description: "Request routing and load balancing", enabled: false },
  { id: "spider", name: "SPIDER", role: "Web Research", description: "Web scraping and data extraction", enabled: false },
  { id: "dume", name: "DUM-E", role: "File Organizer", description: "Desktop cleanup and archive management", enabled: false },
];

const FUTURE_AGENTS: FutureAgent[] = [
  { name: "PEPPER POTTS", role: "Business Intelligence", description: "Strategic planning and ROI analysis" },
  { name: "HAPPY HOGAN", role: "Security Monitor", description: "System security and threat detection" },
  { name: "RHODEY", role: "Hardware Interface", description: "Device management and peripherals" },
];

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

      <div class="settings-welcome" id="settings-welcome" style="display:none">
        <p>Welcome to JARVIS. Let's get you set up.</p>
      </div>

      <div class="settings-body">

        <!-- API Keys -->
        <section class="settings-section" id="section-api-keys">
          <h3>API Keys</h3>

          <div class="settings-field">
            <label>Anthropic API Key</label>
            <div class="settings-input-row">
              <input type="password" id="input-anthropic-key" placeholder="sk-ant-..." />
              <button class="settings-btn" id="btn-test-anthropic">Test</button>
              <span class="status-dot" id="status-anthropic"></span>
            </div>
          </div>

          <div class="settings-actions">
            <button class="settings-btn primary" id="btn-save-keys">Save Keys</button>
          </div>
        </section>

        <!-- Connection Status -->
        <section class="settings-section" id="section-status">
          <h3>Connection Status</h3>
          <div class="status-grid">
            <div class="status-row"><span class="status-dot" id="status-claude-cli"></span><span>Claude Code CLI</span></div>
            <div class="status-row"><span class="status-dot" id="status-calendar"></span><span>Apple Calendar</span></div>
            <div class="status-row"><span class="status-dot" id="status-mail"></span><span>Apple Mail</span></div>
            <div class="status-row"><span class="status-dot" id="status-notes"></span><span>Apple Notes</span></div>
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

          <div class="settings-field">
            <label>Calendar Accounts</label>
            <textarea id="input-calendar-accounts" rows="2" placeholder="auto (or comma-separated emails)"></textarea>
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

        <!-- Agent Configuration -->
        <section class="settings-section" id="section-agents">
          <h3>Multi-Agent System</h3>
          <p style="font-size: 12px; color: #999; margin-bottom: 16px;">Enable or disable AI agents that enhance JARVIS capabilities.</p>

          <div id="agents-list" style="display: flex; flex-direction: column; gap: 12px;">
            <!-- Agent items will be inserted here -->
          </div>

          <div class="settings-actions">
            <button class="settings-btn primary" id="btn-save-agents">Save Agent Configuration</button>
          </div>
        </section>

        <!-- Future Agents -->
        <section class="settings-section" id="section-future-agents">
          <h3>Future Agents (Coming Soon)</h3>
          <p style="font-size: 12px; color: #999; margin-bottom: 16px;">Additional agents planned for future releases.</p>

          <div id="future-agents-list" style="display: flex; flex-direction: column; gap: 12px;">
            <!-- Future agent items will be inserted here -->
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

        <!-- Setup Navigation (first-time only) -->
        <div class="setup-nav" id="setup-nav" style="display:none">
          <button class="settings-btn primary" id="btn-setup-next">Next</button>
        </div>

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

function renderAgentsList() {
  const container = document.getElementById("agents-list");
  if (!container) return;

  container.innerHTML = AGENTS.map(agent => `
    <div style="display: flex; align-items: center; justify-content: space-between; padding: 12px; background: rgba(255,255,255,0.05); border-radius: 6px; border: 1px solid rgba(255,255,255,0.1);">
      <div style="flex: 1;">
        <div style="font-weight: 600; margin-bottom: 4px;">${agent.name}</div>
        <div style="font-size: 11px; color: #aaa;">${agent.role}</div>
        <div style="font-size: 11px; color: #777; margin-top: 2px;">${agent.description}</div>
      </div>
      <div style="margin-left: 12px;">
        <input type="checkbox" id="agent-${agent.id}" ${agent.enabled ? "checked" : ""} ${agent.id === "jarvis" ? "disabled" : ""} style="cursor: pointer; width: 20px; height: 20px;" />
      </div>
    </div>
  `).join("");
}

function renderFutureAgentsList() {
  const container = document.getElementById("future-agents-list");
  if (!container) return;

  container.innerHTML = FUTURE_AGENTS.map(agent => `
    <div style="display: flex; align-items: center; justify-content: space-between; padding: 12px; background: rgba(255,255,255,0.02); border-radius: 6px; border: 1px solid rgba(255,255,255,0.05); opacity: 0.7;">
      <div style="flex: 1;">
        <div style="font-weight: 600; margin-bottom: 4px;">${agent.name}</div>
        <div style="font-size: 11px; color: #aaa;">${agent.role}</div>
        <div style="font-size: 11px; color: #777; margin-top: 2px;">${agent.description}</div>
      </div>
      <div style="margin-left: 12px; font-size: 11px; color: #666; padding: 6px 12px; background: rgba(255,255,255,0.1); border-radius: 4px;">Coming Soon</div>
    </div>
  `).join("");
}

async function loadStatus() {
  try {
    const status = await apiGet<StatusResponse>("/api/settings/status");

    setDotStatus("status-claude-cli", status.claude_code_installed ? "green" : "red");
    setDotStatus("status-calendar", status.calendar_accessible ? "green" : "red");
    setDotStatus("status-mail", status.mail_accessible ? "green" : "red");
    setDotStatus("status-notes", status.notes_accessible ? "green" : "red");
    setDotStatus("status-server", "green");

    const serverDetail = document.getElementById("status-server-detail");
    if (serverDetail) serverDetail.textContent = `port ${status.server_port} | up ${formatUptime(status.uptime_seconds)}`;

    // API key status dot
    setDotStatus("status-anthropic", status.env_keys_set.anthropic ? "green" : "red");

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
    const calEl = document.getElementById("input-calendar-accounts") as HTMLTextAreaElement;
    if (nameEl) nameEl.value = prefs.user_name || "";
    if (honEl) honEl.value = prefs.honorific || "sir";
    if (calEl) calEl.value = prefs.calendar_accounts || "auto";

    // Restore saved color
    if (prefs.orb_color) {
      localStorage.setItem("jarvis-orb-color", prefs.orb_color);
      document.documentElement.style.setProperty("--orb-color", prefs.orb_color);
      console.log("[settings] Restored color:", prefs.orb_color);
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

  // Save keys
  document.getElementById("btn-save-keys")?.addEventListener("click", async () => {
    const anthropicKey = (document.getElementById("input-anthropic-key") as HTMLInputElement).value.trim();

    if (anthropicKey) {
      await apiPost("/api/settings/keys", { key_name: "ANTHROPIC_API_KEY", key_value: anthropicKey });
    }
    await loadStatus();
  });

  // Test Anthropic
  document.getElementById("btn-test-anthropic")?.addEventListener("click", async () => {
    setDotStatus("status-anthropic", "yellow");
    const key = (document.getElementById("input-anthropic-key") as HTMLInputElement).value.trim();
    try {
      const result = await apiPost<{ valid: boolean; error?: string }>("/api/settings/test-llm", { key_value: key || undefined });
      setDotStatus("status-anthropic", result.valid ? "green" : "red");
    } catch {
      setDotStatus("status-anthropic", "red");
    }
  });

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
    const calendar_accounts = (document.getElementById("input-calendar-accounts") as HTMLTextAreaElement).value.trim();
    const orb_color = localStorage.getItem("jarvis-orb-color") || "#4ca8e8";
    await apiPost("/api/settings/preferences", { user_name, honorific, calendar_accounts, orb_color });
    console.log("[settings] Saved preferences including color:", orb_color);
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

  // Agent save
  document.getElementById("btn-save-agents")?.addEventListener("click", async () => {
    const agentStates: Record<string, boolean> = {};
    AGENTS.forEach(agent => {
      const checkbox = document.getElementById(`agent-${agent.id}`) as HTMLInputElement;
      agentStates[agent.id] = checkbox?.checked || agent.id === "jarvis";
    });
    await apiPost("/api/settings/agents", { agents: agentStates });
    console.log("[settings] Saved agent configuration:", agentStates);
  });

  // Setup next button
  document.getElementById("btn-setup-next")?.addEventListener("click", advanceSetup);
}

// ---------------------------------------------------------------------------
// First-time setup wizard
// ---------------------------------------------------------------------------

function enterSetupMode() {
  isFirstTimeSetup = true;
  setupStep = 0;

  const welcome = document.getElementById("settings-welcome");
  if (welcome) welcome.style.display = "block";

  const nav = document.getElementById("setup-nav");
  if (nav) nav.style.display = "flex";

  // Hide sections except API keys
  showSetupStep(0);
}

function showSetupStep(step: number) {
  const sections = ["section-api-keys", "section-status", "section-preferences", "section-sysinfo"];
  sections.forEach((id, i) => {
    const el = document.getElementById(id);
    if (!el) return;
    if (step === 0 && i === 0) el.style.display = "";
    else if (step === 1 && i === 0) el.style.display = "";
    else if (step === 2 && i === 2) el.style.display = "";
    else if (step === 3) el.style.display = "";
    else el.style.display = "none";
  });

  const nextBtn = document.getElementById("btn-setup-next");
  if (nextBtn) {
    if (step === 0) nextBtn.textContent = "Next: Test Keys";
    else if (step === 1) nextBtn.textContent = "Next: Set Your Name";
    else if (step === 2) nextBtn.textContent = "Finish Setup";
    else nextBtn.style.display = "none";
  }
}

async function advanceSetup() {
  setupStep++;
  if (setupStep >= 3) {
    // Done — save everything and close
    isFirstTimeSetup = false;
    const welcome = document.getElementById("settings-welcome");
    if (welcome) welcome.style.display = "none";
    const nav = document.getElementById("setup-nav");
    if (nav) nav.style.display = "none";

    // Show all sections
    ["section-api-keys", "section-status", "section-preferences", "section-sysinfo"].forEach((id) => {
      const el = document.getElementById(id);
      if (el) el.style.display = "";
    });

    closeSettings();
    return;
  }
  showSetupStep(setupStep);
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

  // Render agent lists
  renderAgentsList();
  renderFutureAgentsList();

  // Load data
  const status = await loadStatus();
  await loadPreferences();

  // Check for first-time setup
  if (status && !status.env_keys_set.anthropic) {
    enterSetupMode();
  }
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
  try {
    const status = await apiGet<StatusResponse>("/api/settings/status");
    if (!status.env_keys_set.anthropic) {
      openSettings();
      return true;
    }
  } catch {
    // Server not ready yet, skip
  }
  return false;
}
