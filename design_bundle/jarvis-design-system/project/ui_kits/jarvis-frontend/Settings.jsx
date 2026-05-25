/* Settings — theme selector + custom palette + sliders */

const THEMES = [
  { id: "jarvis", name: "Jarvis", desc: "Default · cyan + orange",  swatches: ["#00d4ff","#ff6b35","#0a1622"] },
  { id: "ultron", name: "Ultron", desc: "Hostile red + amber",      swatches: ["#ff1744","#ff8500","#0a1622"] },
  { id: "friday", name: "Friday", desc: "Rose gold + pink",         swatches: ["#ffb86b","#ff5d8f","#0a1622"] },
  { id: "vision", name: "Vision", desc: "Synthetic green + cyan",   swatches: ["#00ff9c","#00d4ff","#0a1622"] },
  { id: "stark",  name: "Stark",  desc: "Industrial amber + red",   swatches: ["#ffc107","#ff3030","#0a1622"] },
  { id: "mono",   name: "Mono",   desc: "Tactical white · no color",swatches: ["#c4f0ff","#607078","#0a1622"] },
];

function Settings({ onClose, theme, setTheme, custom, setCustom, intensity, setIntensity, gridOpacity, setGridOpacity }) {
  // Custom colors override the theme via inline css vars on document root.
  // The app.jsx persists & applies them; here we just provide controls.

  function applyCustom(key, val) {
    setCustom({ ...custom, [key]: val });
  }
  function resetCustom() {
    setCustom({ primary: "", accent: "" });
  }

  return (
    <div className="settings-shell">
      <div className="rail" style={{ border: 0, padding: 0, marginBottom: 4 }}>
        <div className="dot"></div>
        <span style={{ color: 'var(--primary)' }}>J.A.R.V.I.S.</span>
        <span style={{ color: 'var(--fg-3)' }}>·</span>
        <span className="crumb">SETTINGS <b>// APPEARANCE</b></span>
        <div className="spacer"></div>
        <button className="icon-btn active" onClick={onClose} title="Close settings">
          <span style={{ width: 16, height: 16 }}>{Ic.close}</span>
        </button>
      </div>

      <div style={{
        fontFamily: "var(--font-display)", fontWeight: 700,
        fontSize: 28, letterSpacing: "0.28em", color: "var(--primary)",
        textShadow: "var(--glow-sm)", textTransform: "uppercase",
        marginTop: 8,
      }}>Appearance</div>
      <div className="micro" style={{ color: "var(--fg-3)" }}>SWAP PRESETS · OVERRIDE WITH CUSTOM HEX · TWEAK INTENSITY</div>

      <div className="settings-grid">

        {/* === THEME PRESETS === */}
        <div className="settings-section" style={{ gridColumn: "1 / -1" }}>
          <div className="panel-bracket tl"></div>
          <div className="panel-bracket tr"></div>
          <div className="panel-bracket bl"></div>
          <div className="panel-bracket br"></div>
          <h3 className="section-h">Color Palette</h3>
          <div className="theme-grid">
            {THEMES.map(t => (
              <button key={t.id}
                className={"theme-card" + (theme === t.id ? " selected" : "")}
                onClick={() => setTheme(t.id)}>
                <div className="name">{t.name}</div>
                <div className="desc">{t.desc}</div>
                <div className="swatches">
                  {t.swatches.map((c, i) => (
                    <span key={i} style={{ background: c }}/>
                  ))}
                </div>
              </button>
            ))}
          </div>
        </div>

        {/* === CUSTOM HEX === */}
        <div className="settings-section">
          <div className="panel-bracket tl"></div>
          <div className="panel-bracket tr"></div>
          <div className="panel-bracket bl"></div>
          <div className="panel-bracket br"></div>
          <h3 className="section-h">Custom Hex Override</h3>
          <div className="micro" style={{ color: "var(--fg-3)", marginBottom: 14 }}>
            ENTER A HEX CODE OR PICK A COLOR. OVERRIDES THE SELECTED THEME UNTIL CLEARED.
          </div>

          <ColorField
            label="Primary · signal"
            valueHex={custom.primary || THEMES.find(t => t.id === theme).swatches[0]}
            isCustom={!!custom.primary}
            onChange={v => applyCustom("primary", v)}/>

          <ColorField
            label="Accent · warning"
            valueHex={custom.accent || THEMES.find(t => t.id === theme).swatches[1]}
            isCustom={!!custom.accent}
            onChange={v => applyCustom("accent", v)}/>

          <div className="btn-row">
            <button className="btn ghost" onClick={resetCustom}>↺ Reset custom</button>
          </div>
        </div>

        {/* === INTENSITY === */}
        <div className="settings-section">
          <div className="panel-bracket tl"></div>
          <div className="panel-bracket tr"></div>
          <div className="panel-bracket bl"></div>
          <div className="panel-bracket br"></div>
          <h3 className="section-h">HUD Intensity</h3>

          <div className="slider-row">
            <span>Glow strength</span>
            <input type="range" min="0" max="100" value={intensity}
              onChange={e => setIntensity(+e.target.value)}/>
            <span className="v">{intensity}%</span>
          </div>
          <div className="slider-row">
            <span>Grid opacity</span>
            <input type="range" min="0" max="100" value={gridOpacity}
              onChange={e => setGridOpacity(+e.target.value)}/>
            <span className="v">{gridOpacity}%</span>
          </div>
          <div className="micro" style={{ color: "var(--fg-3)", marginTop: 14 }}>
            ▸ ZERO GLOW + LOW GRID = STEALTH MODE.<br/>
            ▸ HIGH GLOW = COMBAT-READY HUD.
          </div>

          <div className="btn-row" style={{ marginTop: 16 }}>
            <button className="btn ghost" onClick={() => { setIntensity(55); setGridOpacity(60); }}>
              ↺ Reset defaults
            </button>
          </div>
        </div>

        {/* === PREVIEW STRIP === */}
        <div className="settings-section" style={{ gridColumn: "1 / -1" }}>
          <div className="panel-bracket tl"></div>
          <div className="panel-bracket tr"></div>
          <div className="panel-bracket bl"></div>
          <div className="panel-bracket br"></div>
          <h3 className="section-h">Live Preview</h3>
          <div style={{ display: "flex", gap: 24, alignItems: "center", flexWrap: "wrap" }}>
            <MiniGauge value={67} label="LOAD"/>
            <div style={{ flex: 1, minWidth: 260 }}>
              <TeleRow label="POWER"  value={87}/>
              <TeleRow label="SIGNAL" value={64}/>
              <TeleRow label="THRUST" value={42} warn/>
            </div>
            <div className="btn-row" style={{ margin: 0 }}>
              <button className="btn primary">▸ ENGAGE</button>
              <button className="btn accent">⚠ OVERRIDE</button>
              <button className="btn">SCAN</button>
            </div>
          </div>
        </div>

      </div>
    </div>
  );
}

function ColorField({ label, valueHex, onChange, isCustom }) {
  const [text, setText] = useState(valueHex);
  useEffect(() => { setText(valueHex); }, [valueHex]);

  function commit(v) {
    const clean = v.trim();
    if (/^#?[0-9a-f]{6}$/i.test(clean)) {
      const hex = clean.startsWith("#") ? clean : "#" + clean;
      onChange(hex);
    }
  }
  return (
    <div className="hex-field">
      <label>
        <span className="swatch" style={{ background: valueHex }}></span>
        {label}{isCustom && <span style={{ color: "var(--accent)", marginLeft: 6, letterSpacing: "0.2em" }}>· CUSTOM</span>}
      </label>
      <div className="hex-input-wrap">
        <input type="text" value={text}
          onChange={e => setText(e.target.value)}
          onBlur={e => commit(e.target.value)}
          onKeyDown={e => { if (e.key === "Enter") commit(e.target.value); }}
          placeholder="#00d4ff"/>
        <input type="color" value={valueHex}
          onChange={e => onChange(e.target.value)}/>
      </div>
    </div>
  );
}

window.Settings = Settings;
window.THEMES = THEMES;
