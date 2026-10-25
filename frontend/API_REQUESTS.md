# Frontend → Backend: proposed API.md additions

The frontend is built against `mock.json` using the current API.md. These are the extra things it needs. All of them already work in mock mode (see `src/api.js`). Please tell me if you want different names or shapes.

## 1. `GET /homes` takes the scenario inputs (needed for R10)

`GET /homes?wind=60&crews=5`, same response. This lets the simulator sliders recolor the map. Without parameters, use your default storm.

## 2. `GET /backtest` (R12)

```json
{
  "storm": "Feb 13–17, 2025",
  "damage_records": 1223,
  "within_range_pct": 78,
  "summary": "In 78 out of 100 repairs, the real repair finished inside our estimated range."
}
```

## 3. `GET /audit` (R14; already in PLAN.md, missing from API.md)

```json
[
  {
    "time": "2025-02-15T21:04:00",
    "home_id": "043748782",
    "action": "risk_estimate",
    "detail": "High, wind 60 mph, crews 5"
  }
]
```

## 4. Optional: alert channel and timing (the brief asks for "notification timing, channel")

Add to `alert` in `/homes/{id}`:

```json
"alert": { "eligible": true, "escalate": false, "reason": "High risk",
           "channel": "Text message", "timing": "6 hours before the storm" }
```

I'll show these as soon as they show up in the response.

## 5. Message types for `/messages/{id}`

The frontend labels these four `type` values: `pre_storm`, `outage_confirmed`, `estimate_updated`, `restored`. Any other type still shows, just with its raw name.

## Data notes from looking at the files

- The damage `Event` column is `"Default"` on all 1,659 rows, so the Feb storm has to be picked out by `Report_Tim` date.
- Unrepaired damage rows have `Repaired_D` = `2025-10-24`, which is the export date and not a real repair date. Leave those out of the repair-time stats.
- `337574651` is the mock "fallback" home. It would help to have a real home that triggers `fallback` for the demo.

## Other things the frontend expects

- CORS for `http://localhost:5173`
- 404 for an unknown home ID (the UI shows a friendly error)
- `power_path` as `[lat, lon]` pairs, ordered from the home to the substation
