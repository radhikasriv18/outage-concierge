# PowerCheck: AI Outage Concierge

**HackOHI/O 2026 · AEP challenge**

Before a storm hits, PowerCheck tells a customer in plain words: **Will I lose power? How long until it's back? What should I do? Will I get an alert?** Every number comes from a model and repair simulation built on AEP's real data for the Roanoke, VA area, and tested on real storms.

- **Live app:** https://powercheck.vercel.app
- **API docs:** https://powercheck-api.onrender.com/docs

> The backend runs on Render's free tier and sleeps when idle. The first visit after a quiet spell can take about a minute.

## What it does
- **Find your home** by street name or anonymized home ID, on a map colored by outage risk.
- **Chance of losing power**, with how sure we are and why (wind, overhead lines, the weakest equipment on your power path).
- **Restoration estimate** as a time range, your place in the repair line, and what would change it.
- **AI chat** (Gemini) that answers using only the engine's numbers: what to do now, alerts, why a neighbor still has power, generator safety.
- **Storm simulator:** change wind and repair crews and watch the map and answers update. Also shows the backtest and a staff view with alert rules, escalations, and an audit log.

## How it works
1. **Data:** AEP customers, equipment, network chains (home → transformer → fuses/reclosers → breaker), damage records, and labor hours, plus historical storm weather from Open-Meteo.
2. **Risk model:** predicts damage per piece of equipment from wind and local conditions. Trained on two real storms and tested on the third it never saw: the riskiest 10% of equipment had about **1.9×** the average damage.
3. **Home risk:** a home loses power if any equipment on its power path fails.
4. **Repairs:** simulates hundreds of storms with AEP's labor hours (×4.5 for travel and setup) and crew scheduling. Crew count is calibrated to AEP's real Feb 2025 repair records.
5. **Privacy:** street names only (no house numbers), equipment positions rounded to ~100 m, and the AI never sees personal data.

## Try these homes
| Home ID | Shows |
|---|---|
| `606712043` | Medium risk, near the front of the repair line |
| `638817953` | Further back in line, so the crews slider has a clear effect |
| `333164148` | Life-support home: phone call + text, escalated for a welfare check |
| `272000257` | No power-path data: honest "we can't predict this" fallback |

## Run locally
```
# backend (http://localhost:8000)
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --port 8000

# frontend (http://localhost:5173), in a second terminal
cd frontend
npm install
npm run dev
```
The data the API needs is already in `backend/cache/`. To rebuild it from AEP's raw files, unzip `aep_data/data/raw/*.zip` into `aep_data/data/extracted/`, install `geopandas openpyxl`, and run `prep.py`, `build_training.py`, `add_weather.py`, `train_model.py`, and `backtest.py` in that order. The chat needs `GEMINI_API_KEY` in `backend/.env`; without it, it falls back to a plain summary.

## Tech
React, Vite, Tailwind, Leaflet · FastAPI, pandas, scikit-learn · Gemini · Vercel + Render

## Team
Radhika and Sailesh
