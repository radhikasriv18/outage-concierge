# PowerCheck (AI Outage Concierge): frontend

React + Vite + Tailwind + react-leaflet.

```
npm install
npm run dev        # http://localhost:5173
```

## Mock vs real backend
By default it talks to the real backend at http://localhost:8000 (start it first, see `backend/`).
To use the fake data in `src/mock.json` instead (a yellow "Demo data" bar shows at the top), create `.env.local`:
```
VITE_USE_MOCK=true
```
and restart `npm run dev`. All API calls live in `src/api.js`.

## Pages
- `/`: customer screen: map, answer card, 4 questions, facts/estimates/actions, neighbor check, chat
- `/simulator`: wind and crews sliders, staff view + audit log, backtest, privacy/limits panel

Add `?home=043748782` to either URL to preselect a home (useful for demo links).
