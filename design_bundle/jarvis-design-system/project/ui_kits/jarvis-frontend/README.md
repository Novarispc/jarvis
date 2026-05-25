# Jarvis Frontend UI Kit

A high-fidelity web recreation of the iconic J.A.R.V.I.S. HUD aesthetic from the Iron Man wallpaper that inspired this design system.

## Files

- `index.html` — entry, wires up React + Babel + components
- `app.jsx` — top-level state (screen, theme, listening), persistence
- `components.jsx` — shared primitives: `<Panel>`, `<Gauge>`, `<Hex>`, `<TabButton>`, `<ReactorCore>`, `<Bracket>`, icons
- `Dashboard.jsx` — main HUD (telemetry, reactor, app grid, quick links, voice composer)
- `Settings.jsx` — theme switcher: 6 preset palettes + custom hex inputs for primary/accent

## Screens

| Screen | Trigger |
| --- | --- |
| Dashboard | default |
| Settings | top-right ⚙ icon |
| Voice listening | speaker icon / "JARVIS, listen" button |

## Interactions

- Click tab launcher (left rail) → highlight & log to console
- Click hex tile → ripple
- Click ⚙ → settings screen
- In settings, click a palette swatch → live theme swap, persisted to `localStorage`
- Type a hex in primary/accent custom fields → applies as a custom theme on top

## Source-of-truth note

The original repo (kishanrajput23/Jarvis-Desktop-Voice-Assistant) is a Python CLI with no frontend. This kit is built from the visual DNA of the wallpaper, not from existing component code.
