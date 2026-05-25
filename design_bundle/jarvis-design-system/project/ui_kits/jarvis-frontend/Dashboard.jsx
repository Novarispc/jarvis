// Dashboard - Main JARVIS HUD interface
const Dashboard = () => {
  const [activeTab, setActiveTab] = React.useState('JARVIS CORE');
  const [time, setTime] = React.useState(new Date());
  const [orbState, setOrbState] = React.useState('idle'); // 'idle', 'listening', 'thinking'

  React.useEffect(() => {
    const timer = setInterval(() => setTime(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

  // Cycle through orb states for demo
  React.useEffect(() => {
    const states = ['idle', 'thinking', 'listening'];
    let currentIndex = 0;
    const stateTimer = setInterval(() => {
      currentIndex = (currentIndex + 1) % states.length;
      setOrbState(states[currentIndex]);
    }, 5000);
    return () => clearInterval(stateTimer);
  }, []);

  const tabs = [
    { name: 'CONTROL PANEL', color: 'orange' },
    { name: 'STEAM', color: 'orange' },
    { name: 'WHATSAPP', color: 'orange' },
    { name: 'UTORRENT', color: 'orange' },
    { name: 'SKYPE', color: 'orange' },
    { name: 'JARVIS CORE', color: 'cyan' }
  ];

  const formatTime = (date) => {
    const hours = date.getHours().toString().padStart(2, '0');
    const mins = date.getMinutes().toString().padStart(2, '0');
    const secs = date.getSeconds().toString().padStart(2, '0');
    return `${hours}:${mins}:${secs}`;
  };

  return (
    <div className="dashboard">
      {/* Top Header */}
      <header className="top-header">
        <div className="header-left">
          <div className="jarvis-logo">■ J.A.R.V.I.S.</div>
          <div className="header-label">
            <span className="label-text">DESKTOP //</span>
            <span className="label-highlight">HOME</span>
          </div>
        </div>
        
        <div className="header-center">
          <div className="status-pill live">■ LIVE</div>
          <div className="status-pill">UPTIME {formatTime(time).replace(':', 'D ')}</div>
          <div className="status-pill">LAT 12.971° N · LON 77.594° E</div>
          <div className="status-pill">SAT, MAY 23</div>
        </div>

        <div className="header-right">
          <button className="icon-btn">🎤</button>
          <button className="icon-btn">⚙️</button>
        </div>
      </header>

      {/* Main Content */}
      <div className="main-content">
        {/* Left Sidebar - Tab Launchers */}
        <aside className="sidebar-left">
          {tabs.map((tab) => (
            <button
              key={tab.name}
              className={`tab-launcher ${tab.color} ${activeTab === tab.name ? 'active' : ''}`}
              onClick={() => setActiveTab(tab.name)}
            >
              <span className="tab-bullet">▸</span> {tab.name}
            </button>
          ))}
        </aside>

        {/* Center - Main HUD */}
        <main className="center-hud">
          <div className="greeting">
            GOOD EVENING, SIR · <span className="highlight">HOW MAY I ASSIST</span>
          </div>
        </main>

        {/* Right Sidebar */}
        <aside className="sidebar-right">
          {/* System Telemetry */}
          <div className="telemetry-panel">
            <div className="panel-header">■ SYSTEM TELEMETRY</div>
            
            <div className="metric-row">
              <span className="metric-label">CPU</span>
              <div className="metric-bar">
                <div className="metric-fill" style={{width: '70%'}}></div>
              </div>
            </div>
            
            <div className="metric-row">
              <span className="metric-label">MEMORY</span>
              <div className="metric-bar">
                <div className="metric-fill" style={{width: '85%'}}></div>
              </div>
            </div>
            
            <div className="metric-row">
              <span className="metric-label">DISK</span>
              <div className="metric-bar">
                <div className="metric-fill" style={{width: '45%'}}></div>
              </div>
            </div>
            
            <div className="metric-row">
              <span className="metric-label">GPU</span>
              <div className="metric-bar">
                <div className="metric-fill" style={{width: '60%'}}></div>
              </div>
            </div>
            
            <div className="metric-row">
              <span className="metric-label">SIGNAL</span>
              <div className="metric-bar">
                <div className="metric-fill" style={{width: '92%'}}></div>
              </div>
            </div>

            <div className="telemetry-values">
              <div className="value-large">47.2</div>
              <div className="value-large">0.0</div>
            </div>
            <div className="telemetry-labels">
              <div className="value-label">CPU<br/>°C</div>
              <div className="value-label">GPU<br/>°C</div>
            </div>
          </div>

          {/* Launcher */}
          <div className="launcher-panel">
            <div className="panel-header">■ LAUNCHER</div>
            
            <div className="launcher-grid">
              <button className="launcher-btn">
                <div className="launcher-icon">▶</div>
                <div className="launcher-label">MEDIA</div>
              </button>
              
              <button className="launcher-btn">
                <div className="launcher-icon">📷</div>
                <div className="launcher-label">VISION</div>
              </button>
              
              <button className="launcher-btn">
                <div className="launcher-icon">☁</div>
                <div className="launcher-label">CLOUD</div>
              </button>
            </div>
          </div>
        </aside>
      </div>

      {/* Bottom Left - Circular Gauge */}
      <div className="bottom-gauge">
        <svg viewBox="0 0 120 120" className="gauge-svg">
          <circle cx="60" cy="60" r="50" className="gauge-bg" />
          <circle cx="60" cy="60" r="50" className="gauge-progress" 
                  style={{strokeDasharray: '314', strokeDashoffset: '94'}} />
          <circle cx="60" cy="60" r="35" className="gauge-inner" />
        </svg>
      </div>
    </div>
  );
};

window.Dashboard = Dashboard;
