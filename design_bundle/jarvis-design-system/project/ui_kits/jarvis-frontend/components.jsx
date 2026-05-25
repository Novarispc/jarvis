/* ============================================================
   JARVIS — shared component primitives
   Exposed to window so other babel scripts can use them.
   ============================================================ */
const { useState, useEffect, useRef, useMemo } = React;

/* Panel ------------------------------------------------------ */
function Panel({ title, meta, bright, children, style }) {
  return (
    <div className={"panel" + (bright ? " bright" : "")} style={style}>
      <div className="panel-bracket tl"></div>
      <div className="panel-bracket tr"></div>
      <div className="panel-bracket bl"></div>
      <div className="panel-bracket br"></div>
      {title && (
        <div className="panel-head">
          <div className="dot"></div>
          <h3>{title}</h3>
          {meta && <div className="meta">{meta}</div>}
        </div>
      )}
      {children}
    </div>
  );
}

/* Hex Cell -------------------------------------------------- */
function HexCell({ icon, label, variant, onClick, active }) {
  const cls = ["hex-cell"];
  if (variant) cls.push(variant);
  if (active) cls.push("active");
  return (
    <button className={cls.join(" ")} onClick={onClick}>
      {icon}
      {label && <span>{label}</span>}
    </button>
  );
}

/* Tab Button (angled launcher) ----------------------------- */
function TabButton({ label, variant = "accent", onClick, active }) {
  const cls = ["tab-btn"];
  if (variant === "cyan") cls.push("cyan");
  if (variant === "muted") cls.push("muted");
  if (active) cls.push("active");
  return (
    <button className={cls.join(" ")} onClick={onClick}>
      ▸ {label}
    </button>
  );
}

/* Tele Row (telemetry bar) --------------------------------- */
function TeleRow({ label, value, max = 100, unit = "%", warn }) {
  const pct = Math.min(100, (value / max) * 100);
  return (
    <div className={"tele-row" + (warn ? " warn" : "")}>
      <span>{label}</span>
      <div className="bar"><div className="fill" style={{ width: pct + "%" }}></div></div>
      <span className="val">{value}{unit}</span>
    </div>
  );
}

/* Numeric tile --------------------------------------------- */
function NumericTile({ value, label, color }) {
  return (
    <div className="numeric-tile">
      <div className="big" style={color ? { color } : null}>{value}</div>
      <div className="lbl">{label}</div>
    </div>
  );
}

/* Reactor Core (big animated central piece) ---------------- */
function ReactorCore() {
  return (
    <div style={{ width: 420, height: 420, position: "relative" }}>
      <svg viewBox="0 0 100 100" style={{ width: "100%", height: "100%", display: "block" }}>
        <defs>
          <radialGradient id="rg" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor="var(--primary)" stopOpacity="0.55"/>
            <stop offset="60%" stopColor="var(--primary)" stopOpacity="0.05"/>
            <stop offset="100%" stopColor="transparent"/>
          </radialGradient>
        </defs>

        {/* outer rotating dashed ring */}
        <g style={{ transformOrigin: "50% 50%", animation: "spin 40s linear infinite" }}>
          <circle cx="50" cy="50" r="48" fill="none" stroke="var(--primary)" strokeWidth="0.4" strokeDasharray="1 2" opacity="0.6"/>
          <circle cx="50" cy="50" r="45" fill="none" stroke="var(--primary)" strokeWidth="0.3" strokeDasharray="4 1" opacity="0.5"/>
        </g>

        {/* tick band */}
        <g>
          {Array.from({ length: 72 }).map((_, i) => {
            const a = (i * 5) * Math.PI / 180;
            const r1 = 42, r2 = i % 6 === 0 ? 36 : i % 2 === 0 ? 39 : 40.5;
            const x1 = 50 + Math.cos(a) * r1, y1 = 50 + Math.sin(a) * r1;
            const x2 = 50 + Math.cos(a) * r2, y2 = 50 + Math.sin(a) * r2;
            return <line key={i} x1={x1} y1={y1} x2={x2} y2={y2}
              stroke="var(--primary)" strokeWidth="0.3"
              opacity={i % 6 === 0 ? 1 : 0.45}/>;
          })}
        </g>

        {/* counter-spinning sector arcs */}
        <g style={{ transformOrigin: "50% 50%", animation: "spin 24s linear infinite reverse" }}>
          <path d="M 50 16 A 34 34 0 0 1 84 50" fill="none" stroke="var(--primary)" strokeWidth="1" />
          <path d="M 50 84 A 34 34 0 0 1 16 50" fill="none" stroke="var(--primary)" strokeWidth="1" />
          <circle cx="84" cy="50" r="1" fill="var(--accent)"/>
          <circle cx="16" cy="50" r="1" fill="var(--accent)"/>
        </g>

        {/* inner hexagon-on-circle */}
        <circle cx="50" cy="50" r="28" fill="none" stroke="var(--primary)" strokeWidth="0.5" opacity="0.6"/>
        <polygon points="50,24 73,38 73,62 50,76 27,62 27,38" fill="none" stroke="var(--primary)" strokeWidth="0.5" opacity="0.55"/>
        <polygon points="50,30 67,40 67,60 50,70 33,60 33,40" fill="none" stroke="var(--primary)" strokeWidth="0.4" opacity="0.4"/>

        {/* central glow disc */}
        <circle cx="50" cy="50" r="22" fill="url(#rg)"/>
        <circle cx="50" cy="50" r="16" fill="none" stroke="var(--primary)" strokeWidth="0.8"/>
        <circle cx="50" cy="50" r="11" fill="var(--primary)" opacity="0.25"/>
        <circle cx="50" cy="50" r="11" fill="none" stroke="var(--primary)" strokeWidth="1"/>

        {/* triskelion blades */}
        <g style={{ transformOrigin: "50% 50%", animation: "spin 18s linear infinite" }}>
          {[0, 120, 240].map(deg => (
            <g key={deg} transform={`rotate(${deg} 50 50)`}>
              <path d="M 50 40 Q 56 50 50 60 Q 44 50 50 40 Z" fill="var(--primary)" opacity="0.45"/>
            </g>
          ))}
        </g>

        {/* center bright dot */}
        <circle cx="50" cy="50" r="3" fill="var(--primary)" style={{ filter: "drop-shadow(0 0 6px var(--primary))" }}/>

        {/* crosshair */}
        <line x1="2"  y1="50" x2="14" y2="50" stroke="var(--primary)" strokeWidth="0.5"/>
        <line x1="86" y1="50" x2="98" y2="50" stroke="var(--primary)" strokeWidth="0.5"/>
        <line x1="50" y1="2"  x2="50" y2="14" stroke="var(--primary)" strokeWidth="0.5"/>
        <line x1="50" y1="86" x2="50" y2="98" stroke="var(--primary)" strokeWidth="0.5"/>
      </svg>
    </div>
  );
}

/* Small radial gauge (for side panel) ---------------------- */
function MiniGauge({ value, label, color = "var(--primary)" }) {
  const circ = 2 * Math.PI * 36;
  const len = (value / 100) * circ * 0.75;
  return (
    <div style={{ width: 90, height: 90, position: "relative" }}>
      <svg viewBox="0 0 100 100" style={{ width: "100%", height: "100%" }}>
        <circle cx="50" cy="50" r="42" fill="none" stroke="var(--border-1)" strokeWidth="1"/>
        <circle cx="50" cy="50" r="36" fill="none" stroke="var(--border-1)" strokeWidth="1"/>
        <circle cx="50" cy="50" r="36" fill="none" stroke={color} strokeWidth="4"
          strokeDasharray={`${len} ${circ}`} strokeLinecap="butt"
          style={{ transform: "rotate(-90deg)", transformOrigin: "50% 50%", filter: `drop-shadow(0 0 4px ${color})` }}/>
        {Array.from({ length: 24 }).map((_, i) => {
          const a = (i * 15) * Math.PI / 180;
          const x1 = 50 + Math.cos(a) * 44, y1 = 50 + Math.sin(a) * 44;
          const x2 = 50 + Math.cos(a) * 47, y2 = 50 + Math.sin(a) * 47;
          return <line key={i} x1={x1} y1={y1} x2={x2} y2={y2} stroke={color} strokeWidth="0.6" opacity="0.7"/>;
        })}
      </svg>
      <div style={{
        position: "absolute", inset: 0,
        display: "flex", flexDirection: "column",
        alignItems: "center", justifyContent: "center",
        fontFamily: "var(--font-mono)",
      }}>
        <div style={{ fontSize: 18, color, fontVariantNumeric: "tabular-nums" }}>{value}</div>
        <div style={{ fontSize: 8, letterSpacing: "0.22em", color: "var(--fg-3)", textTransform: "uppercase" }}>{label}</div>
      </div>
    </div>
  );
}

/* JARVIS logo lockup (bottom-left of dashboard) ----------- */
function JarvisLogo() {
  return (
    <div style={{ width: "100%", height: "100%", position: "relative" }}>
      <svg viewBox="0 0 200 200" style={{ width: "100%", height: "100%" }}>
        {/* Outer tick ring */}
        {Array.from({ length: 60 }).map((_, i) => {
          const a = (i * 6) * Math.PI / 180;
          const r1 = 94, r2 = i % 5 === 0 ? 86 : 90;
          const x1 = 100 + Math.cos(a) * r1, y1 = 100 + Math.sin(a) * r1;
          const x2 = 100 + Math.cos(a) * r2, y2 = 100 + Math.sin(a) * r2;
          return <line key={i} x1={x1} y1={y1} x2={x2} y2={y2}
            stroke="var(--primary)" strokeWidth="0.8" opacity={i % 5 === 0 ? 0.9 : 0.4}/>;
        })}
        {/* labels at quarters */}
        {["100","80","60","40","20","0","20","40","60","80","100"].map((t, idx) => {
          const angle = (idx * 18 - 90) * Math.PI / 180;
          const x = 100 + Math.cos(angle) * 78;
          const y = 100 + Math.sin(angle) * 78 + 3;
          return <text key={idx} x={x} y={y} textAnchor="middle"
            fontFamily="var(--font-mono)" fontSize="7" fill="var(--accent)"
            opacity="0.7">{t}</text>;
        })}
        {/* arc highlight */}
        <circle cx="100" cy="100" r="74" fill="none" stroke="var(--primary)" strokeWidth="1"
          strokeDasharray="80 300" style={{ transformOrigin: "50% 50%", animation: "spin 30s linear infinite" }}/>
        {/* inner disc */}
        <circle cx="100" cy="100" r="66" fill="var(--surface-1)" stroke="var(--primary)" strokeWidth="1"/>
        <circle cx="100" cy="100" r="60" fill="none" stroke="var(--primary)" strokeWidth="0.5" opacity="0.5"/>
        <circle cx="100" cy="100" r="50" fill="var(--primary)" opacity="0.12"/>
        <circle cx="100" cy="100" r="50" fill="none" stroke="var(--primary)" strokeWidth="0.8"/>
        {/* yellow arc segment */}
        <path d="M 100 30 A 70 70 0 0 1 158 80" fill="none"
          stroke="var(--accent)" strokeWidth="2"
          style={{ filter: "drop-shadow(0 0 4px var(--accent))" }}/>
        {/* wordmark */}
        <text x="100" y="106" textAnchor="middle"
          fontFamily="var(--font-display)" fontSize="20" fontWeight="900"
          letterSpacing="4" fill="var(--primary)"
          style={{ filter: "drop-shadow(0 0 4px var(--primary))" }}>JARVIS</text>
      </svg>
    </div>
  );
}

/* Icons -------------------------------------------------- */
const Ic = {
  power:    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M12 2v10"/><path d="M5.6 7.6a8 8 0 1 0 12.8 0"/></svg>,
  mic:      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5 11a7 7 0 0 0 14 0"/><line x1="12" y1="18" x2="12" y2="22"/></svg>,
  gear:     <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3h0a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8v0a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"/></svg>,
  close:    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><line x1="5" y1="5" x2="19" y2="19"/><line x1="19" y1="5" x2="5" y2="19"/></svg>,
  send:     <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22,2 15,22 11,13 2,9"/></svg>,
  search:   <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><circle cx="11" cy="11" r="7"/><line x1="21" y1="21" x2="16" y2="16"/></svg>,
  globe:    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><circle cx="12" cy="12" r="9"/><line x1="3" y1="12" x2="21" y2="12"/><path d="M12 3a15 15 0 0 1 0 18M12 3a15 15 0 0 0 0 18"/></svg>,
  play:     <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M5 3l16 9-16 9z"/></svg>,
  folder:   <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M3 7a1 1 0 0 1 1-1h5l2 2h9a1 1 0 0 1 1 1v10a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1z"/></svg>,
  cam:      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M3 7h4l2-2h6l2 2h4v12H3z"/><circle cx="12" cy="13" r="4"/></svg>,
  cpu:      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><rect x="6" y="6" width="12" height="12" rx="1"/><rect x="9" y="9" width="6" height="6"/><line x1="9" y1="3" x2="9" y2="6"/><line x1="15" y1="3" x2="15" y2="6"/><line x1="9" y1="18" x2="9" y2="21"/><line x1="15" y1="18" x2="15" y2="21"/><line x1="3" y1="9" x2="6" y2="9"/><line x1="3" y1="15" x2="6" y2="15"/><line x1="18" y1="9" x2="21" y2="9"/><line x1="18" y1="15" x2="21" y2="15"/></svg>,
  cloud:    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M6 18a4 4 0 1 1 .9-7.9A6 6 0 0 1 19 12a3 3 0 0 1 0 6z"/></svg>,
  bolt:     <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><polygon points="13,2 4,14 11,14 10,22 20,10 13,10"/></svg>,
  warn:     <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M12 2L2 22h20L12 2z"/><line x1="12" y1="10" x2="12" y2="15"/><circle cx="12" cy="18" r="0.5" fill="currentColor"/></svg>,
  refresh:  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><polyline points="23,4 23,10 17,10"/><polyline points="1,20 1,14 7,14"/><path d="M3.5 9a9 9 0 0 1 15-3.5L23 10M1 14l4.5 4.5A9 9 0 0 0 20.5 15"/></svg>,
};

Object.assign(window, {
  Panel, HexCell, TabButton, TeleRow, NumericTile,
  ReactorCore, MiniGauge, JarvisLogo, Ic
});
