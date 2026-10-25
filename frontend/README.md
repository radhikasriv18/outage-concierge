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
- `/`: street or home-ID search, risk map, answer card ("Will I lose power?" / "How long?"), at a glance, AI chat
- `/simulator`: wind and crew sliders, scenario summary, backtest, staff view + audit log

Add `?home=606712043` to either URL to preselect a home (useful for demo links).

## Deploy
Hosted on Vercel (project `powercheck`). From this folder: `npx vercel --prod`.
`VITE_API_URL` is set in the Vercel project to the Render backend.
