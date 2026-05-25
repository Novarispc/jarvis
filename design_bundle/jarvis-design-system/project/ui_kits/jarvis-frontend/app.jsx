/* App shell — screen state + theme/custom-color/intensity persistence */

function App() {
  const [screen, setScreen]       = useState("dashboard"); // dashboard | settings
  const [listening, setListening] = useState(false);

  const [theme, setTheme] = useState(() => localStorage.getItem("jv.theme") || "jarvis");
  const [custom, setCustom] = useState(() => {
    try { return JSON.parse(localStorage.getItem("jv.custom") || '{"primary":"","accent":""}'); }
    catch { return { primary: "", accent: "" }; }
  });
  const [intensity, setIntensity]   = useState(() => +(localStorage.getItem("jv.glow") || 55));
  const [gridOpacity, setGridOpacity] = useState(() => +(localStorage.getItem("jv.grid") || 60));

  /* Apply theme attribute on <html> */
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem("jv.theme", theme);
  }, [theme]);

  /* Apply custom color overrides */
  useEffect(() => {
    const root = document.documentElement;
    if (custom.primary) {
      root.style.setProperty("--primary", custom.primary);
      root.style.setProperty("--primary-glow", hexToRgba(custom.primary, 0.55));
      root.style.setProperty("--primary-deep", shadeHex(custom.primary, -0.35));
      root.style.setProperty("--primary-soft", shadeHex(custom.primary, 0.35));
    } else {
      root.style.removeProperty("--primary");
      root.style.removeProperty("--primary-glow");
      root.style.removeProperty("--primary-deep");
      root.style.removeProperty("--primary-soft");
    }
    if (custom.accent) {
      root.style.setProperty("--accent", custom.accent);
      root.style.setProperty("--accent-glow", hexToRgba(custom.accent, 0.55));
      root.style.setProperty("--accent-deep", shadeHex(custom.accent, -0.35));
      root.style.setProperty("--accent-soft", shadeHex(custom.accent, 0.35));
    } else {
      root.style.removeProperty("--accent");
      root.style.removeProperty("--accent-glow");
      root.style.removeProperty("--accent-deep");
      root.style.removeProperty("--accent-soft");
    }
    localStorage.setItem("jv.custom", JSON.stringify(custom));
  }, [custom]);

  /* Apply intensity + grid sliders by overriding glow + grid-line tokens */
  useEffect(() => {
    const root = document.documentElement;
    const i = intensity / 100;
    // Override the glow tokens by reading current primary/accent
    const primary = getComputedStyle(root).getPropertyValue("--primary").trim();
    const accent  = getComputedStyle(root).getPropertyValue("--accent").trim();
    root.style.setProperty("--glow-sm", `0 0 ${8 * i + 1}px ${hexToRgba(primary, 0.55 * i + 0.05)}`);
    root.style.setProperty("--glow-md", `0 0 ${16 * i + 2}px ${hexToRgba(primary, 0.55 * i + 0.05)}, 0 0 2px ${primary}`);
    root.style.setProperty("--glow-lg", `0 0 ${32 * i + 2}px ${hexToRgba(primary, 0.55 * i + 0.05)}, 0 0 4px ${primary}`);
    root.style.setProperty("--glow-accent", `0 0 ${16 * i + 2}px ${hexToRgba(accent, 0.55 * i + 0.05)}, 0 0 2px ${accent}`);
    localStorage.setItem("jv.glow", String(intensity));
  }, [intensity, theme, custom]);

  useEffect(() => {
    const root = document.documentElement;
    const g = gridOpacity / 100;
    const primary = getComputedStyle(root).getPropertyValue("--primary").trim();
    root.style.setProperty("--grid-line",      hexToRgba(primary, 0.06 * g + 0.005));
    root.style.setProperty("--grid-line-bold", hexToRgba(primary, 0.12 * g + 0.01));
    localStorage.setItem("jv.grid", String(gridOpacity));
  }, [gridOpacity, theme, custom]);

  return (
    <React.Fragment>
      <Dashboard
        onOpenSettings={() => setScreen("settings")}
        onListen={() => setListening(l => !l)}
        listening={listening}/>
      {screen === "settings" && (
        <Settings
          onClose={() => setScreen("dashboard")}
          theme={theme} setTheme={setTheme}
          custom={custom} setCustom={setCustom}
          intensity={intensity} setIntensity={setIntensity}
          gridOpacity={gridOpacity} setGridOpacity={setGridOpacity}/>
      )}
    </React.Fragment>
  );
}

/* tiny color utils ---------------------------------------------------- */
function hexToRgba(hex, a) {
  let h = (hex || "").replace("#", "").trim();
  if (h.length === 3) h = h.split("").map(c => c + c).join("");
  if (!/^[0-9a-f]{6}$/i.test(h)) return `rgba(0,212,255,${a})`;
  const r = parseInt(h.slice(0,2), 16);
  const g = parseInt(h.slice(2,4), 16);
  const b = parseInt(h.slice(4,6), 16);
  return `rgba(${r},${g},${b},${a})`;
}
function shadeHex(hex, lum) {  // lum -1..1
  let h = (hex || "").replace("#", "").trim();
  if (h.length === 3) h = h.split("").map(c => c + c).join("");
  if (!/^[0-9a-f]{6}$/i.test(h)) return hex;
  let out = "#";
  for (let i = 0; i < 3; i++) {
    let c = parseInt(h.substr(i * 2, 2), 16);
    c = Math.round(Math.min(Math.max(0, c + (lum < 0 ? c * lum : (255 - c) * lum)), 255));
    out += c.toString(16).padStart(2, "0");
  }
  return out;
}

ReactDOM.createRoot(document.getElementById("root")).render(<App/>);
