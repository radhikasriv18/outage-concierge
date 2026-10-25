# Outage Concierge: frontend

React + Vite + Tailwind + react-leaflet.

```
npm install
npm run dev        # http://localhost:5173
```

## Mock vs real backend
It uses `src/mock.json` by default (a yellow "Demo data" bar shows at the top).
To use the real backend, create `.env.local`:
```
VITE_USE_MOCK=false
VITE_API_URL=http://localhost:8000
```
and restart `npm run dev`. All API calls live in `src/api.js`.

## Pages
- `/`: customer screen: map, answer card, 4 questions, facts/estimates/actions, neighbor check, chat
- `/simulator`: wind and crews sliders, staff view + audit log, backtest, privacy/limits panel

Add `?home=043748782` to either URL to preselect a home (useful for demo links).
