// JarvisSystem - Complete AI interface with all design elements
const JarvisSystem = () => {
  const [time, setTime] = React.useState(new Date());
  const [orbState, setOrbState] = React.useState('idle'); // 'idle', 'listening', 'thinking'
  const [reactorOnline, setReactorOnline] = React.useState(true);
  const [reactorCharge, setReactorCharge] = React.useState(100);
  const [metrics, setMetrics] = React.useState({
    cpu: 67,
    memory: 73,
    disk: 48,
    gpu: 82,
    signal: 91,
    uptime: { days: 0, hours: 20, mins: 34 }
  });

  const greeting = "GOOD EVENING, SIR · HOW MAY I ASSIST";

  React.useEffect(() => {
    const timer = setInterval(() => setTime(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

  // Reactor animation - exciting charge/discharge with dynamic effects
  React.useEffect(() => {
    const reactorTimer = setInterval(() => {
      setReactorCharge(prev => {
        if (reactorOnline) {
          // Charging up - exponential acceleration with bursts
          if (prev >= 100) {
            setTimeout(() => setReactorOnline(false), 1500);
            return 100;
          }
          // Multi-stage charging: slow start, rapid mid, controlled finish
          let speed;
          if (prev < 20) {
            speed = 0.5; // Slow ignition
          } else if (prev < 80) {
            speed = 3 + (prev - 20) / 10; // Rapid acceleration
          } else {
            speed = 2 - (prev - 80) / 20; // Controlled finish
          }
          return Math.min(100, prev + speed);
        } else {
          // Discharging - multi-stage power down
          if (prev <= 0) {
            setTimeout(() => setReactorOnline(true), 1500);
            return 0;
          }
          // Dramatic discharge stages
          let speed;
          if (prev > 80) {
            speed = 4; // Rapid initial drop
          } else if (prev > 40) {
            speed = 2.5; // Steady decline
          } else if (prev > 10) {
            speed = 1.5; // Slow drain
          } else {
            speed = 0.3; // Final flicker
          }
          return Math.max(0, prev - speed);
        }
      });
    }, 40);
    return () => clearInterval(reactorTimer);
  }, [reactorOnline]);

  // Simulate metric updates
  React.useEffect(() => {
    const metricTimer = setInterval(() => {
      setMetrics(prev => ({
        ...prev,
        cpu: Math.min(100, Math.max(0, prev.cpu + (Math.random() - 0.5) * 10)),
        memory: Math.min(100, Math.max(0, prev.memory + (Math.random() - 0.5) * 5)),
        signal: Math.min(100, Math.max(0, prev.signal + (Math.random() - 0.5) * 8))
      }));
    }, 3000);
    return () => clearInterval(metricTimer);
  }, []);

  const formatTime = (date) => {
    const hours = date.getHours().toString().padStart(2, '0');
    const mins = date.getMinutes().toString().padStart(2, '0');
    const secs = date.getSeconds().toString().padStart(2, '0');
    return `${hours}:${mins}:${secs}`;
  };

  const formatDate = (date) => {
    const days = ['SUN', 'MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT'];
    const months = ['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN', 'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC'];
    return `${days[date.getDay()]}, ${months[date.getMonth()]} ${date.getDate()}`;
  };

  const toggleVoice = () => {
    if (orbState === 'listening') {
      setOrbState('thinking');
      setTimeout(() => setOrbState('idle'), 2000);
    } else {
      setOrbState('listening');
    }
  };

  return (
    <div className="jarvis-system">
      {/* Top Header */}
      <header className="top-header">
        <div className="jarvis-title">J.A.R.V.I.S.</div>
        <div className="system-status">
          <div className="status-pill live">LIVE</div>
          <div className="status-pill">{formatTime(time)}</div>
          <div className="status-pill">{formatDate(time)}</div>
          <div className="status-pill">LAT 12.971° N · LON 77.594° E</div>
        </div>
      </header>

      {/* Left Panel - Controls & Launchers */}
      <aside className="left-panel">
        <div className="panel">
          <div className="panel-header">
            <div className="panel-dot"></div>
            <div className="panel-title">QUICK LAUNCH</div>
          </div>
          <div className="launcher-grid">
            <div className="hex-btn">A</div>
            <div className="hex-btn">B</div>
            <div className="hex-btn">C</div>
            <div className="hex-btn">D</div>
            <div className="hex-btn">E</div>
            <div className="hex-btn">F</div>
          </div>
        </div>

        <div className="panel">
          <div className="panel-header">
            <div className="panel-dot"></div>
            <div className="panel-title">REACTOR STATUS</div>
          </div>
          <div style={{display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '12px'}}>
            {/* Status text outside */}
            <div style={{display: 'flex', gap: '20px', fontFamily: 'var(--font-mono)', fontSize: '11px'}}>
              <div style={{
                color: reactorOnline ? 'var(--primary)' : 'var(--fg-3)',
                textShadow: reactorOnline ? '0 0 8px var(--primary-glow)' : 'none',
                fontWeight: 600,
                letterSpacing: '0.2em',
                transition: 'all 0.3s ease'
              }}>
                {reactorOnline ? '● ONLINE' : '○ OFFLINE'}
              </div>
              <div style={{
                color: reactorCharge > 50 ? 'var(--primary)' : 'var(--accent)',
                letterSpacing: '0.15em'
              }}>
                {Math.round(reactorCharge)}%
              </div>
            </div>

            {/* Reactor gauge */}
            <div className="gauge" style={{width: '140px', height: '140px'}}>
              <svg viewBox="0 0 100 100">
                {/* Outer rings */}
                <circle cx="50" cy="50" r="46" fill="none" stroke="var(--primary)" strokeWidth="2" 
                  opacity={reactorOnline ? 0.9 : 0.3}
                  style={{transition: 'opacity 0.3s ease'}}/>
                <circle cx="50" cy="50" r="38" fill="none" stroke="var(--border-2)" strokeWidth="1"/>
                <circle cx="50" cy="50" r="32" fill="none" stroke="var(--border-2)" strokeWidth="1"/>
                
                {/* Multiple animated charging rings with different speeds */}
                <circle cx="50" cy="50" r="28" fill="none" stroke="var(--primary)" strokeWidth="2"
                  style={{
                    strokeDasharray: '176',
                    strokeDashoffset: `${176 * (1 - reactorCharge / 100)}`,
                    transform: 'rotate(-90deg)',
                    transformOrigin: '50% 50%',
                    filter: `drop-shadow(0 0 ${8 + reactorCharge / 10}px var(--primary-glow))`,
                    transition: 'none',
                    opacity: reactorOnline ? (0.6 + reactorCharge / 250) : 0.2
                  }}/>
                
                <circle cx="50" cy="50" r="22" fill="none" stroke="var(--primary)" strokeWidth="4"
                  style={{
                    strokeDasharray: '138',
                    strokeDashoffset: `${138 * (1 - reactorCharge / 100)}`,
                    transform: 'rotate(-90deg)',
                    transformOrigin: '50% 50%',
                    filter: `drop-shadow(0 0 ${12 + reactorCharge / 5}px var(--primary-glow))`,
                    transition: 'none'
                  }}/>
                
                {/* Inner ring pulses at different rate */}
                <circle cx="50" cy="50" r="16" fill="none" stroke="var(--primary)" strokeWidth="2"
                  style={{
                    strokeDasharray: '100',
                    strokeDashoffset: `${100 * (1 - reactorCharge / 100)}`,
                    transform: 'rotate(90deg)',
                    transformOrigin: '50% 50%',
                    filter: `drop-shadow(0 0 ${6 + reactorCharge / 8}px var(--primary-glow))`,
                    transition: 'none',
                    opacity: 0.8
                  }}/>
                
                {/* Spinning accent rings when charging - multiple for effect */}
                {reactorOnline && reactorCharge < 100 && (
                  <>
                    <circle cx="50" cy="50" r="35" fill="none" stroke="var(--accent)" strokeWidth="1.5"
                      style={{
                        strokeDasharray: '30 190',
                        transform: 'rotate(0deg)',
                        transformOrigin: '50% 50%',
                        animation: 'spin 1s linear infinite',
                        opacity: 0.7
                      }}/>
                    <circle cx="50" cy="50" r="30" fill="none" stroke="var(--primary)" strokeWidth="1"
                      style={{
                        strokeDasharray: '20 170',
                        transform: 'rotate(180deg)',
                        transformOrigin: '50% 50%',
                        animation: 'spin 1.5s linear infinite reverse',
                        opacity: 0.5
                      }}/>
                  </>
                )}
                
                {/* Energy field when charging fast (mid-range) */}
                {reactorOnline && reactorCharge > 20 && reactorCharge < 80 && (
                  <circle cx="50" cy="50" r="40" fill="none" stroke="var(--primary)" strokeWidth="0.5"
                    style={{
                      strokeDasharray: '10 15',
                      opacity: 0.3,
                      animation: 'spin 2s linear infinite'
                    }}/>
                )}
                
                {/* Core layers with dynamic intensity */}
                <circle cx="50" cy="50" r="14" fill="var(--primary)" 
                  opacity={reactorOnline ? (0.1 + reactorCharge / 300) : 0.02}
                  style={{transition: 'opacity 0.05s ease'}}/>
                <circle cx="50" cy="50" r="14" fill="none" stroke="var(--primary)" strokeWidth="2"
                  opacity={reactorOnline ? 1 : 0.3}
                  style={{
                    transition: 'opacity 0.2s ease',
                    filter: reactorCharge > 80 ? `drop-shadow(0 0 8px var(--primary-glow))` : 'none'
                  }}/>
                
                {/* Multi-layer pulsing center core */}
                <circle cx="50" cy="50" r="8" fill="var(--primary)" 
                  style={{
                    filter: `drop-shadow(0 0 ${reactorOnline ? 8 + (reactorCharge / 5) : 1}px var(--primary-glow))`,
                    opacity: reactorOnline ? (0.6 + reactorCharge / 200) : 0.15,
                    transition: 'all 0.05s ease',
                    animation: reactorOnline && reactorCharge < 100 ? 'corePulse 0.4s ease-in-out infinite' : 'none'
                  }}/>
                <circle cx="50" cy="50" r="4" fill="white" 
                  style={{
                    filter: `drop-shadow(0 0 ${reactorOnline ? 12 + (reactorCharge / 3) : 2}px var(--primary-glow))`,
                    opacity: reactorOnline ? (0.8 + reactorCharge / 500) : 0.1,
                    animation: reactorOnline && reactorCharge > 20 && reactorCharge < 100 ? 'corePulse 0.3s ease-in-out infinite' : 'none'
                  }}/>
                
                {/* Crosshairs */}
                <line x1="2" y1="50" x2="14" y2="50" stroke="var(--primary)" strokeWidth="1" 
                  opacity={reactorOnline ? 1 : 0.3}/>
                <line x1="86" y1="50" x2="98" y2="50" stroke="var(--primary)" strokeWidth="1"
                  opacity={reactorOnline ? 1 : 0.3}/>
                <line x1="50" y1="2" x2="50" y2="14" stroke="var(--primary)" strokeWidth="1"
                  opacity={reactorOnline ? 1 : 0.3}/>
                <line x1="50" y1="86" x2="50" y2="98" stroke="var(--primary)" strokeWidth="1"
                  opacity={reactorOnline ? 1 : 0.3}/>
                
                {/* Energy burst particles - more dynamic */}
                {reactorCharge >= 95 && reactorOnline && (
                  <>
                    {/* Cardinal directions */}
                    <circle cx="50" cy="20" r="2.5" fill="var(--primary)" opacity="0.9"
                      style={{animation: 'burst1 0.8s ease-out infinite', filter: 'drop-shadow(0 0 4px var(--primary-glow))'}}/>
                    <circle cx="80" cy="50" r="2.5" fill="var(--primary)" opacity="0.9"
                      style={{animation: 'burst2 0.8s ease-out infinite 0.2s', filter: 'drop-shadow(0 0 4px var(--primary-glow))'}}/>
                    <circle cx="50" cy="80" r="2.5" fill="var(--primary)" opacity="0.9"
                      style={{animation: 'burst3 0.8s ease-out infinite 0.4s', filter: 'drop-shadow(0 0 4px var(--primary-glow))'}}/>
                    <circle cx="20" cy="50" r="2.5" fill="var(--primary)" opacity="0.9"
                      style={{animation: 'burst4 0.8s ease-out infinite 0.6s', filter: 'drop-shadow(0 0 4px var(--primary-glow))'}}/>
                    
                    {/* Diagonal directions */}
                    <circle cx="65" cy="35" r="2" fill="var(--accent)" opacity="0.8"
                      style={{animation: 'burst1 1s ease-out infinite 0.1s'}}/>
                    <circle cx="65" cy="65" r="2" fill="var(--accent)" opacity="0.8"
                      style={{animation: 'burst2 1s ease-out infinite 0.3s'}}/>
                    <circle cx="35" cy="65" r="2" fill="var(--accent)" opacity="0.8"
                      style={{animation: 'burst3 1s ease-out infinite 0.5s'}}/>
                    <circle cx="35" cy="35" r="2" fill="var(--accent)" opacity="0.8"
                      style={{animation: 'burst4 1s ease-out infinite 0.7s'}}/>
                  </>
                )}
                
                {/* Flickering discharge sparks when powering down */}
                {!reactorOnline && reactorCharge > 5 && reactorCharge < 40 && (
                  <>
                    <circle cx="50" cy="30" r="1.5" fill="var(--accent)" opacity="0.6"
                      style={{animation: 'flicker 0.3s ease-in-out infinite'}}/>
                    <circle cx="60" cy="50" r="1" fill="var(--accent)" opacity="0.5"
                      style={{animation: 'flicker 0.4s ease-in-out infinite 0.1s'}}/>
                    <circle cx="40" cy="55" r="1" fill="var(--primary)" opacity="0.4"
                      style={{animation: 'flicker 0.35s ease-in-out infinite 0.2s'}}/>
                  </>
                )}
              </svg>
            </div>
          </div>
        </div>
      </aside>

      {/* Center Display */}
      <main className="center-display">
        <div className="greeting-text">
          GOOD EVENING, SIR · <span className="highlight">HOW MAY I ASSIST</span>
        </div>
      </main>

      {/* Right Panel - Telemetry */}
      <aside className="right-panel">
        <div className="panel">
          <div className="panel-header">
            <div className="panel-dot"></div>
            <div className="panel-title">SYSTEM TELEMETRY</div>
          </div>
          
          <div className="gauges-row">
            {/* CPU Gauge */}
            <div className="gauge">
              <svg viewBox="0 0 100 100">
                <circle cx="50" cy="50" r="46" fill="none" stroke="var(--border-1)" strokeWidth="1"/>
                <circle cx="50" cy="50" r="40" fill="none" stroke="var(--border-1)" strokeWidth="1"/>
                <circle cx="50" cy="50" r="36" fill="none" stroke="var(--primary)" strokeWidth="6"
                  style={{
                    strokeDasharray: '152 226',
                    strokeDashoffset: `-${152 * (1 - metrics.cpu / 100)}`,
                    transform: 'rotate(-90deg)',
                    transformOrigin: '50% 50%',
                    filter: 'drop-shadow(0 0 6px var(--primary-glow))'
                  }}/>
                <circle cx="50" cy="50" r="36" fill="none" stroke="var(--border-1)" strokeWidth="1"
                  style={{
                    strokeDasharray: '152 226',
                    strokeDashoffset: '-152',
                    transform: 'rotate(-90deg)',
                    transformOrigin: '50% 50%'
                  }}/>
                <circle cx="50" cy="50" r="2" fill="var(--primary)"/>
              </svg>
              <div className="gauge-center">
                <div className="gauge-value">{Math.round(metrics.cpu)}</div>
                <div className="gauge-unit">CPU %</div>
              </div>
            </div>

            {/* GPU Gauge */}
            <div className="gauge">
              <svg viewBox="0 0 100 100">
                <circle cx="50" cy="50" r="46" fill="none" stroke="var(--border-1)" strokeWidth="1"/>
                <path d="M50 50 L 50 4 A46 46 0 0 1 96 50 Z" fill="var(--accent)" opacity="0.7"/>
                <path d="M50 50 L 96 50 A46 46 0 0 1 50 96 Z" fill="var(--accent)" opacity="0.45"/>
                <circle cx="50" cy="50" r="32" fill="var(--surface-1)"/>
                <circle cx="50" cy="50" r="32" fill="none" stroke="var(--primary)" strokeWidth="2"/>
                <circle cx="50" cy="50" r="20" fill="none" stroke="var(--border-1)" strokeWidth="1"/>
                <circle cx="50" cy="50" r="3" fill="var(--accent)"/>
              </svg>
              <div className="gauge-center">
                <div className="gauge-value" style={{color: 'var(--accent)'}}>{Math.round(metrics.gpu)}</div>
                <div className="gauge-unit" style={{color: 'var(--accent)'}}>GPU %</div>
              </div>
            </div>
          </div>

          <div className="status-bars" style={{marginTop: '20px'}}>
            <div className="status-row">
              <div className="status-label">MEMORY</div>
              <div className="status-bar">
                <div className="status-fill" style={{width: `${metrics.memory}%`}}></div>
              </div>
              <div className="status-value">{Math.round(metrics.memory)}%</div>
            </div>

            <div className="status-row">
              <div className="status-label">DISK</div>
              <div className="status-bar">
                <div className="status-fill warn" style={{width: `${metrics.disk}%`}}></div>
              </div>
              <div className="status-value warn">{metrics.disk} GB</div>
            </div>

            <div className="status-row">
              <div className="status-label">SIGNAL</div>
              <div className="status-bar">
                <div className="status-fill" style={{width: `${metrics.signal}%`}}></div>
              </div>
              <div className="status-value">{Math.round(metrics.signal)}%</div>
            </div>
          </div>
        </div>

        <div className="panel">
          <div className="panel-header">
            <div className="panel-dot"></div>
            <div className="panel-title">POWER DISTRIBUTION</div>
          </div>
          <div className="gauges-row">
            <div className="gauge">
              <svg viewBox="0 0 100 100">
                <circle cx="50" cy="50" r="40" fill="none" stroke="var(--border-1)" strokeWidth="1"/>
                <circle cx="50" cy="50" r="30" fill="none" stroke="var(--primary)" strokeWidth="4"
                  style={{
                    strokeDasharray: '125 188',
                    strokeDashoffset: '-50',
                    transform: 'rotate(-90deg)',
                    transformOrigin: '50% 50%',
                    filter: 'drop-shadow(0 0 4px var(--primary-glow))'
                  }}/>
              </svg>
              <div className="gauge-center">
                <div className="gauge-value">78</div>
                <div className="gauge-unit">CORE</div>
              </div>
            </div>
            <div className="gauge">
              <svg viewBox="0 0 100 100">
                <circle cx="50" cy="50" r="40" fill="none" stroke="var(--border-1)" strokeWidth="1"/>
                <circle cx="50" cy="50" r="30" fill="none" stroke="var(--accent)" strokeWidth="4"
                  style={{
                    strokeDasharray: '100 188',
                    strokeDashoffset: '-70',
                    transform: 'rotate(-90deg)',
                    transformOrigin: '50% 50%',
                    filter: 'drop-shadow(0 0 4px var(--accent-glow))'
                  }}/>
              </svg>
              <div className="gauge-center">
                <div className="gauge-value" style={{color: 'var(--accent)'}}>54</div>
                <div className="gauge-unit" style={{color: 'var(--accent)'}}>AUX</div>
              </div>
            </div>
          </div>
        </div>
      </aside>

      {/* Bottom Status Bar */}
      <footer className="bottom-bar">
        <div className="diagnostics">
          <div className="diag-item">
            <div className="diag-label">UPTIME</div>
            <div className="diag-value">{metrics.uptime.days}D {metrics.uptime.hours}H {metrics.uptime.mins}M</div>
          </div>
          <div className="diag-item">
            <div className="diag-label">CORE TEMP</div>
            <div className="diag-value">54°C</div>
          </div>
          <div className="diag-item">
            <div className="diag-label">NETWORK</div>
            <div className="diag-value">OPTIMAL</div>
          </div>
          <div className="diag-item">
            <div className="diag-label">PROTOCOL</div>
            <div className="diag-value">v4.7.3</div>
          </div>
        </div>

        <div className="voice-controls">
          <button className={`voice-btn ${orbState === 'listening' ? 'active' : ''}`} onClick={toggleVoice}>
            🎤
          </button>
          <button className="voice-btn">⚙️</button>
        </div>
      </footer>
    </div>
  );
};

window.JarvisSystem = JarvisSystem;
