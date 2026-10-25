# API

Backend: `uvicorn main:app --reload` → http://localhost:8000 (interactive docs at `/docs`).
CORS allows `http://localhost:5173` and `http://127.0.0.1:5173`.

**Home IDs are always strings** and can start with `0` (e.g. `"084264074"`). Never convert them to numbers.

## Shared query parameters
| Param | Meaning | Default | Allowed |
|---|---|---|---|
| `wind` | Storm's average wind gust (mph) | real Feb 2025 average (see `/weather`) | 20–100 |
| `crews` | Repair crews in the area | 10 | 1–50 |

Out-of-range values return **422**. Unknown home IDs return **404** with `{"detail": "..."}`.
A new `wind`/`crews` combination takes ~2 s the first time (simulation), then it's cached. Call the API when the user **releases** a slider, not on every move.

---

## GET /homes?wind=&crews=
Every demo home for the map (~5,237: 5,190 in the demo area + 47 real customers with no power path).
```json
[{ "home_id": "606712043", "lat": 37.281836, "lon": -79.896988,
   "risk_band": "Medium", "probability": 0.256 }]
```
`risk_band` is `High`, `Medium`, `Low`, or `Unknown` (no power path → show gray). `probability` is `null` for `Unknown`.

## GET /homes/{home_id}?wind=&crews=
Everything for the answer card.
```json
{
  "home_id": "606712043",
  "headline": "Your power might go out during this storm.",
  "risk": {
    "band": "Medium",
    "probability": 0.256,
    "confidence": "Somewhat sure",
    "doubts": ["Your home is close to the line between two risk levels"],
    "reasons": ["Strong wind gusts of about 56 mph are expected", "..."]
  },
  "restoration": {
    "range_text": "Sun 6 PM – Mon 1:30 AM",
    "min_hours": 2.8,
    "max_hours": 10.5,
    "queue_position": 3,
    "what_changes_it": ["Your repair is near the front of the line, so more crews wouldn't change your time much",
                        "If winds are 10 mph weaker: your chance of losing power drops from 26% to 6%"]
  },
  "facts": ["Storm scenario: wind gusts of about 56 mph in your area", "Your power lines are above ground (from AEP records)"],
  "estimates": ["Medium chance of losing power (about 26%). Somewhat sure.", "..."],
  "actions": ["Charge your phone and a backup battery now", "SAFETY: Stay far away from fallen power lines..."],
  "alert": {
    "eligible": true,
    "channel": "Text message",
    "timing": "6 hours before the storm",
    "reason": "Medium risk of losing power",
    "escalate": false,
    "escalate_reasons": []
  },
  "power_path": [[37.281836, -79.896988], [37.282, -79.897], [37.281, -79.897]],
  "fallback": null,
  "profile_is_synthetic": true
}
```
Notes:
- `confidence` is `Fairly sure`, `Somewhat sure`, or `Not sure` (never higher: the model is only moderately accurate on unseen storms).
- `restoration` values can be `null` when the home almost never loses power in the simulation.
- `actions` starting with `SAFETY:` are safety items → highlight them.
- `power_path` goes from the home (exact) up toward the substation (equipment rounded to ~100 m for privacy).

**Fallback homes** (no power path in AEP's data, e.g. `"272000257"`) return a smaller object:
```json
{
  "home_id": "272000257",
  "headline": "We can't give a reliable prediction for your home right now.",
  "fallback": "We can't predict this home reliably right now, because we don't have details about the equipment that feeds it.",
  "facts": ["Storm scenario: wind gusts of about 57 mph in your area"],
  "estimates": [],
  "actions": ["Charge your phone and a backup battery now", "..."],
  "power_path": [[37.233761, -80.026754]],
  "profile_is_synthetic": true
}
```
If `fallback` is not `null`, show the fallback card (no `risk`, `restoration`, or `alert`).

## GET /neighbor?home=&neighbor=&wind=
`neighbor` is optional: leave it out to use the nearest home on a different branch.
```json
{
  "home": "606712043", "neighbor": "473269434",
  "same_line": false,
  "shared_equipment": 4,
  "my_probability": 0.256, "neighbor_probability": 0.257,
  "explanation": "You and your neighbor are on different transformers, and you share the bigger equipment upstream (4 pieces). ..."
}
```
`same_line` is `null` when one home has no power path.

## GET /messages/{home_id}?wind=&crews=
The 4 alert texts. Empty list `[]` for fallback homes.
```json
[
  { "type": "pre_storm", "text": "AEP: A strong storm arrives Sun 9 AM. ..." },
  { "type": "outage_confirmed", "text": "AEP: Your power is out. ..." },
  { "type": "estimate_updated", "text": "AEP: Update: more damage was found on your line. ..." },
  { "type": "restored", "text": "AEP: Your power is back. ..." }
]
```

## GET /rules
```json
{ "alert_rules": ["High risk: text 12 hours before the storm", "..."],
  "escalation_rules": ["Life support + Medium or High risk: add to AEP's welfare-check list before the storm", "..."],
  "risk_bands": { "High": "30% or more", "Medium": "10%-30%", "Low": "under 10%" } }
```

## GET /weather
```json
{ "storm": "Feb 2025, Roanoke VA", "source": "Open-Meteo historical archive",
  "max_gust_mph": 55.3, "max_gust_time": "2025-02-16T15:00",
  "max_wind_mph": 30.1, "total_rain_in": 2.6,
  "average_gust_across_area_mph": 55.8, "slider_default_mph": 55.8 }
```
Use `slider_default_mph` as the wind slider's starting value.

## GET /backtest
```json
{ "method": "Leave one storm out: trained on two real storms, tested on the third",
  "chosen_model": "logistic_regression",
  "average_roc_auc": 0.619, "average_top10_lift": 1.9,
  "per_storm": [{ "model": "logistic_regression", "test_storm": "feb2025", "damaged_share": 0.042,
                  "roc_auc": 0.638, "avg_precision": 0.06, "brier": 0.04, "lift_top10": 1.89 }],
  "summary": "On storms it had never seen, the equipment our model flagged as riskiest (top 10%) had about 1.9 times the average damage." }
```
(A restoration-time backtest may be added later.)

## GET /audit?limit=50
Newest first.
```json
[{ "time": "2026-10-25T00:26:42", "home_id": "084264074", "action": "risk_estimate",
   "detail": "High (38%), Fairly sure, wind 60 mph, crews 8" }]
```
`action` is one of `risk_estimate`, `escalation`, `fallback`, `messages_generated`, `chat_question`, `chat_fallback`.

## POST /chat
Send:
```json
{ "home_id": "606712043", "question": "Can I run my generator in the garage?", "wind": 55.8, "crews": 10 }
```
(`wind` and `crews` optional; `question` 1–500 characters.)
Get:
```json
{ "answer": "No. Run it outside only, far from windows..." }
```
Uses Gemini (`GEMINI_API_KEY` and `GEMINI_MODEL` in `backend/.env`). If Gemini is unavailable, `answer` is a safe template summary instead, so the UI never breaks.