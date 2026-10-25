# API (backend runs at http://localhost:8000)

## GET /homes
Homes for the map.
```json
[{ "home_id": "H-1042", "lat": 37.27, "lon": -79.94, "risk_band": "High" }]
```

## GET /homes/{home_id}?wind=60&crews=5
Everything for the answer card.
```json
{
  "home_id": "H-1042",
  "headline": "Your power will likely go out tonight.",
  "risk": { "band": "High", "confidence": "Fairly sure",
            "reasons": ["Strong wind expected", "Overhead wires", "Damage on this line in past storms"] },
  "restoration": { "range_text": "2 AM – 10 AM", "min_hours": 6, "max_hours": 14,
                   "queue_position": 4, "what_changes_it": ["2 more crews: 4–9 hours"] },
  "facts": ["Storm warning for your area"],
  "estimates": ["High chance of outage tonight"],
  "actions": ["Charge your phone", "Test your sump pump backup"],
  "alert": { "eligible": true, "escalate": false, "reason": "High risk" },
  "power_path": [[37.27, -79.94], [37.28, -79.93]],
  "fallback": null
}
```

## GET /neighbor?home=H-1042&neighbor=H-1043
```json
{ "same_line": false, "explanation": "Your home is behind a damaged safety switch. Your neighbor's home is on a different line." }
```

## GET /messages/{home_id}
```json
[{ "type": "pre_storm", "text": "AEP: Strong storm tonight. High outage risk for your home..." }]
```

## POST /chat
Send: `{ "home_id": "H-1042", "question": "Is my generator safe?" }`
Get: `{ "answer": "..." }`