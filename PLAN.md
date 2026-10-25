# Outage Concierge: Team Plan

HackOHI/O 2026 · AEP Challenge · Team: Radhika (backend + data) and Sailesh (frontend)

---

## 1. What we're building

A website where a customer picks their home before or during a storm and gets clear, honest answers in plain words:

1. **Will I lose power?**
2. **How long until it's back?**
3. **What should I do?**
4. **Will you alert me?**

**Pitch in one line:** AEP's outage map shows dots *after* the power goes out. Our assistant tells you *before* the storm, in plain words, why, how long, and what to do, and it's tested on AEP's real storm data.

### What makes ours different
1. **"Why does my neighbor have power and I don't?"** Compare two homes' network chains and find where they split.
2. **"Your place in the repair line."** Like a pizza tracker, from a real repair order.
3. **Backtested on the real Feb 2025 storm.** Proves our estimates are honest.
4. **Built for people who can't read outage maps.** Plain words, simple colors, clock times.
5. **AI that only talks, never invents numbers.** All numbers come from our engine.

---

## 2. Tech stack

| Part | Tool |
|---|---|
| Frontend | React (Vite) |
| Map | react-leaflet |
| Styling | Tailwind CSS (AEP-style red buttons) |
| Routing | react-router-dom |
| Backend | FastAPI (Python) + uvicorn |
| Data | pandas + geopandas |
| Weather | Open-Meteo (free, no key) |
| AI assistant | Claude API (`anthropic`), called from the backend only |
| Code sharing | GitHub |

---

## 3. Repo structure

```
outage-concierge/
├── PLAN.md                 ← this file
├── API.md                  ← data format between backend and frontend
├── .gitignore
├── aep_data/               ← AEP's files
│   ├── data/raw/           ← zips (in GitHub)
│   ├── data/extracted/     ← unzipped (NOT in GitHub; unzip locally)
│   ├── data/Install_Labor_HackOHIO.xlsx
│   └── docs/               ← challenge brief + structure drawings PDF
├── backend/
│   ├── prep.py             ← load + clean data
│   ├── engine.py           ← risk, repair time, alerts, privacy filter, audit log
│   ├── messages.py         ← plain-language text
│   ├── main.py             ← FastAPI endpoints
│   └── .env                ← Claude API key (NOT in GitHub)
└── frontend/               ← React app
    └── src/
        ├── pages/          ← MainScreen.jsx, Simulator.jsx
        ├── components/     ← Map, AnswerCard, Chat, Sliders
        └── mock.json       ← fake data until the backend is ready
```

---

## 4. Setup

### Both
```
git clone https://github.com/radhikasriv18/outage-concierge
cd outage-concierge
Expand-Archive aep_data\data\raw\Data1.zip -DestinationPath aep_data\data\extracted\Data1
Expand-Archive aep_data\data\raw\Data2.zip -DestinationPath aep_data\data\extracted\Data2
Expand-Archive aep_data\data\raw\matched_upstream.zip -DestinationPath aep_data\data\extracted\matched_upstream
```

### Backend (Radhika)
```
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install fastapi uvicorn pandas geopandas requests openpyxl anthropic python-dotenv
uvicorn main:app --reload
```
API docs: http://localhost:8000/docs

### Frontend (Sailesh)
```
npm create vite@latest frontend -- --template react
cd frontend
npm install
npm install react-leaflet leaflet react-router-dom
npm run dev
```
App: http://localhost:5173

---

## 5. How the pieces connect

```
React (browser, :5173)  ──request──►  FastAPI (:8000)  ──►  engine.py + data
        ◄────────────── JSON (format in API.md) ─────────────
```

The AI chat goes through the backend: the backend sends Claude the engine's numbers, and Claude only rewrites them into friendly words.

---

## 6. Screens

**Main screen (customer)**
- Left: map of Roanoke, homes colored green / yellow / red; search by home ID or click; the selected home's power path is highlighted
- Right: big answer sentence → 4 buttons → Facts / Estimates / What to do boxes → "Why does my neighbor have power?" → AI chat box

**Simulator page (judges)**
- Storm strength + crews sliders; map and answers update live
- Staff view (technical details + audit log)
- Backtest result
- "How we handle privacy, safety, uncertainty, and limits" panel

---

## 7. The data (what we learned)

- **Location:** Roanoke, Virginia (AEP's Appalachian Power). Real GPS points.
- **Customers:** 117,642 homes. Use `premise_nu` (ID), `kind_of_se` (Overhead / Underground), `critical_c` (113 are "LS Life Support"), `circuit_id`.
- **Network chains** (`matched_upstream.txt`): first column = customer `premise_nu` (100% match). Each tab-separated item looks like `type*id*kind*location_number`. Chain order: transformer → fuses / reclosers → circuit breaker (always last).
- **Chain equipment → map:** match the chain item's location number to `location_n` in the equipment files.
- **Damage records:** 1,659. The **Feb 13–17, 2025 storm** has 1,223 records. That's our demo storm. Damage uses circuit names like `CIR60`; translate with `circuit_id` ↔ `aep_circui` in `Primary_ExportFeatures`.
- **Repair times:** dates only (not hours). Half fixed within 1 day, most within 3.
- **Labor Excel:** pole install ~1.9–3.4 hrs by size; access problems +0.5 hrs; **multiply all hours by 4.5** for travel, safety, and setup.
- **Not in the data:** weather (we add real Feb 2025 weather + a slider), household details (we add synthetic profiles, clearly labeled).
- ⚠️ 117k homes is too many for a web map. Use 1–3 circuits with the most Feb 2025 damage.

---

## 8. Task lists

### First 30 minutes (together)
- [ ] Agree on `API.md`
- [ ] Ask the AEP mentor: person-hours or crew-hours? Any alert rules? How does judging work and how long is the pitch?

### Radhika: backend + data

**Data (`prep.py`)**
- [ ] Load customers, chains, damage records, labor Excel → R1
- [ ] Pick 1–3 demo circuits
- [ ] Add synthetic profiles (sump pump, medical device, elderly), labeled "synthetic"
- [ ] Get real Feb 2025 Roanoke weather (Open-Meteo) → R10
- ✅ Check: print one home with its chain, profile, and real wind speed

**Engine (`engine.py`)**
- [ ] Risk → Low / Med / High + confidence + top 3 reasons → R2, R7
- [ ] Fallback when data is missing → R11
- [ ] Repair time: labor × 4.5 ÷ crews, priority order → range → R3, R12
- [ ] "What would change it" → R3
- [ ] Repair line position ⭐
- [ ] Neighbor comparison ⭐
- [ ] Alert + escalation rules → R5
- [ ] Privacy filter + audit log → R14
- [ ] Backtest on Feb 2025 damage → R12 ⭐
- ✅ Check: changing wind or crews changes the result

**Text (`messages.py`)**
- [ ] Plain sentences + clock times → R9
- [ ] Facts / Estimates / What to do → R8
- [ ] Personalized prep tips → R4
- [ ] 4 alert messages: pre-storm, outage confirmed, time updated, restored → R6

**API (`main.py`)**
- [ ] `/homes`, `/homes/{id}`, `/neighbor`, `/messages/{id}`, `/weather`, `/audit`
- [ ] CORS for `http://localhost:5173`
- [ ] `/chat` with Claude API (engine numbers only) → R13
- ✅ Check: everything works at http://localhost:8000/docs

### Sailesh: frontend

**Setup**
- [ ] Vite + React, react-leaflet, react-router, Tailwind
- [ ] `mock.json` copied from `API.md`
- ✅ Check: app runs at http://localhost:5173

**Main screen**
- [ ] Map with homes colored by risk → R1
- [ ] Search by ID + click a home → R1
- [ ] Highlight the home's power path ⭐
- [ ] Big answer sentence → R2, R9
- [ ] 4 buttons → R2–R5
- [ ] Facts / Estimates / What to do boxes → R8
- [ ] Neighbor view ⭐
- [ ] Alert messages view → R6
- [ ] Chat box → R13

**Simulator page**
- [ ] Storm + crews sliders → R10
- [ ] Map and answers update → R10
- [ ] Staff view + audit log → R14
- [ ] Backtest result → R12
- [ ] "How we handle it" panel → R15

**Look and feel**
- [ ] AEP-style colors, large text, simple words → R9
- [ ] Works on a phone screen

**Connect**
- [ ] Swap `mock.json` for real API calls when the backend is ready

### Last 3–4 hours (together)
- [ ] Every rubric row ✅
- [ ] Test with a non-technical person (answer in 10 seconds?)
- [ ] Slides: problem → demo → what's different → privacy and limits → next steps
- [ ] Practice the pitch twice
- [ ] Submit on Devpost

---

## 9. Rubric tracker

Source: AEP challenge brief. The brief has no point-based rubric; these come from its Minimum Viable Demonstration, Challenge Requirements, Recommended Output Design, and Suggested Technical Components.

| # | Requirement | Where | Done |
|---|---|---|---|
| R1 | Pick an anonymized location | Map click / ID search | ⬜ |
| R2 | Risk band + confidence + explanation | Answer card | ⬜ |
| R3 | Restoration range + what moves it | "How long?" + repair line | ⬜ |
| R4 | Personalized prep and safety tips | "What do I do?" | ⬜ |
| R5 | Alert eligibility + escalation rules | "Will you alert me?" | ⬜ |
| R6 | At least one proactive message | Alert messages | ⬜ |
| R7 | Explain why, protect privacy | Reasons + privacy filter | ⬜ |
| R8 | Separate facts / estimates / actions | Three boxes | ⬜ |
| R9 | Plain language, accessible | Whole app | ⬜ |
| R10 | Judges change an input and see the result | Simulator sliders | ⬜ |
| R11 | Fallback when unsure | Fallback message | ⬜ |
| R12 | Operational realism | Labor × 4.5, repair order, backtest | ⬜ |
| R13 | AI assistant | Chat via Claude API | ⬜ |
| R14 | Controls: validation, thresholds, escalation, privacy filter, audit trail | Engine + staff view | ⬜ |
| R15 | Show privacy, safety, uncertainty, limits | "How we handle it" panel + slide | ⬜ |

**How judges likely think ("Why This Challenge Matters"):** customer impact · utility modernization · operational realism · responsible AI.

---

## 10. Git workflow

- Radhika edits only `backend/`. Sailesh edits only `frontend/`. Shared files (`API.md`, `PLAN.md`): tell each other before changing.
- **Before you start:** `git pull`
- **Every hour (or after each working piece):**
  ```
  git add .
  git commit -m "short description"
  git push
  ```
- If `git push` is rejected: run `git pull`, then push again.
- If the API format changes: update `API.md` first, then tell your teammate.
- **Never commit:** `.env` (API key), `aep_data/data/extracted/`, `node_modules/`.

## 11. Sync points
1. After setup: `API.md` agreed
2. When `/homes/{id}` works: Sailesh switches from mock to real data
3. 3–4 hours before the deadline: **stop adding features**, test everything together

## 12. Rules for us
- Make it work first, ugly is fine. Polish later.
- Simplify the words, never the facts.
- If stuck for more than 20 minutes, ask for help.