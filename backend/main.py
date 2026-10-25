"""
main.py - the API the React frontend talks to.

Run:
    uvicorn main:app --reload
Try it in the browser:
    http://localhost:8000/docs
"""
from datetime import datetime
import json
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

import requests
from dotenv import load_dotenv

load_dotenv()            # reads GEMINI_API_KEY from backend/.env (never commit that file)

import engine
import messages

CACHE = Path(__file__).parent / "cache"
AUDIT_FILE = CACHE / "audit.jsonl"

app = FastAPI(title="Outage Concierge API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# input validation: sliders can't send impossible storms
Wind = Query(engine.REAL_STORM_GUST, ge=20, le=100, description="Storm's average wind gust (mph)")
Crews = Query(engine.DEFAULT_CREWS, ge=1, le=50, description="Repair crews in the area")


# ------------------------------------------------------------------ controls
def audit(home_id, action, detail):
    """Audit trail: every prediction is written down with its inputs."""
    entry = {"time": datetime.now().isoformat(timespec="seconds"),
             "home_id": home_id, "action": action, "detail": detail}
    with open(AUDIT_FILE, "a") as f:
        f.write(json.dumps(entry) + "\n")


def privacy_filter(answer):
    """Customers see their own home exactly, but equipment positions only roughly (~100 m),
    and never internal equipment IDs, other customers, or crew details."""
    if answer.get("power_path"):
        home, *equipment = answer["power_path"]
        answer["power_path"] = [home] + [[round(lat, 3), round(lon, 3)] for lat, lon in equipment]
    return answer


def get_answer(home_id, wind, crews):
    ans = messages.build_answer(home_id, wind, crews)
    if ans is None:
        raise HTTPException(404, f"We couldn't find home {home_id} in the demo area.")
    return ans


# ------------------------------------------------------------------ endpoints
@app.get("/homes")
def homes(wind: float = Wind, crews: int = Crews):
    """Every demo home with its risk band, for the map."""
    a = engine.assess_all(wind)
    h = engine.HOMES[["lat", "lon"]].reset_index()
    out = h.merge(a, on="home_id")
    return [{"home_id": r.home_id, "lat": round(r.lat, 6), "lon": round(r.lon, 6),
             "risk_band": r.band,
             "probability": None if r.probability != r.probability else round(r.probability, 3)}
            for r in out.itertuples()]


@app.get("/homes/{home_id}")
def home(home_id: str, wind: float = Wind, crews: int = Crews):
    """Everything for one home's answer card."""
    ans = get_answer(home_id, wind, crews)
    if not ans.get("fallback"):
        audit(home_id, "risk_estimate",
              f"{ans['risk']['band']} ({ans['risk']['probability']:.0%}), "
              f"{ans['risk']['confidence']}, wind {round(wind)} mph, crews {crews}")
        if ans["alert"]["escalate"]:
            audit(home_id, "escalation", "; ".join(ans["alert"]["escalate_reasons"]))
    else:
        audit(home_id, "fallback", ans["fallback"])
    return privacy_filter(ans)


@app.get("/neighbor")
def neighbor(home: str, neighbor: str | None = None, wind: float = Wind):
    """Why one home might lose power while the neighbor keeps it.
    Leave `neighbor` empty to use the closest home on a different branch."""
    if home not in engine.HOMES.index:
        raise HTTPException(404, f"We couldn't find home {home} in the demo area.")
    other = neighbor or engine.nearest_neighbor(home)
    if other not in engine.HOMES.index:
        raise HTTPException(404, f"We couldn't find home {other} in the demo area.")
    return engine.compare_neighbors(home, other, wind)


@app.get("/messages/{home_id}")
def alert_texts(home_id: str, wind: float = Wind, crews: int = Crews):
    get_answer(home_id, wind, crews)          # 404 if unknown
    msgs = messages.alert_messages(home_id, wind, crews)
    audit(home_id, "messages_generated", f"{len(msgs)} messages")
    return msgs


@app.get("/rules")
def rules():
    """The documented alert and escalation rules."""
    return {"alert_rules": engine.ALERT_RULES, "escalation_rules": engine.ESCALATION_RULES,
            "risk_bands": {"High": f"{engine.HIGH:.0%} or more", "Medium": f"{engine.MEDIUM:.0%}-{engine.HIGH:.0%}",
                           "Low": f"under {engine.MEDIUM:.0%}"}}


@app.get("/weather")
def weather():
    w = json.loads((CACHE / "weather.json").read_text())
    w.pop("hourly", None)
    w["average_gust_across_area_mph"] = engine.REAL_STORM_GUST
    w["slider_default_mph"] = engine.REAL_STORM_GUST
    return w


@app.get("/backtest")
def backtest():
    """How our predictions compared with what really happened."""
    r = json.loads((CACHE / "model_report.json").read_text())
    chosen = [x for x in r["average"] if x["model"] == r["chosen_model"]][0]
    out = {
        "method": "Leave one storm out: trained on two real storms, tested on the third",
        "chosen_model": r["chosen_model"],
        "average_roc_auc": chosen["roc_auc"],
        "average_top10_lift": chosen["lift_top10"],
        "per_storm": [x for x in r["results"] if x["model"] == r["chosen_model"]],
        "summary": (f"On storms it had never seen, the equipment our model flagged as riskiest "
                    f"(top 10%) had about {chosen['lift_top10']:.1f} times the average damage."),
    }
    bt_file = CACHE / "backtest.json"
    if bt_file.exists():
        bt = json.loads(bt_file.read_text())
        out["home_level"] = bt["risk"]
        out["home_level_note"] = (
            "Homes share upstream equipment, so one damaged safety switch can affect over a "
            "thousand homes. In our area each storm had only a handful of independent causes, "
            "too few to judge home-level accuracy. The equipment-level test above is the "
            "meaningful one.")
        out["restoration"] = bt["restoration"]
        rest = bt["restoration"]
        out["restoration_summary"] = (
            f"In the real Feb 2025 storm, {rest['real_done_same_or_next_day']:.0%} of repairs were "
            f"done the same or next day. We set the default crew count to match that.")
    return out


@app.get("/audit")
def audit_log(limit: int = Query(50, ge=1, le=500)):
    if not AUDIT_FILE.exists():
        return []
    lines = AUDIT_FILE.read_text().strip().splitlines()[-limit:]
    return [json.loads(l) for l in reversed(lines)]


# ------------------------------------------------------------------ AI chat
class ChatRequest(BaseModel):
    home_id: str
    question: str = Field(min_length=1, max_length=500)
    wind: float = Field(engine.REAL_STORM_GUST, ge=20, le=100)
    crews: int = Field(engine.DEFAULT_CREWS, ge=1, le=50)


CHAT_RULES = """You are AEP's storm outage assistant, talking to a residential customer.
Answer in plain, calm, simple English (short sentences, no jargon), in 2-5 sentences.
Use ONLY the facts below about this customer's home. Never invent or change numbers,
times, or chances, even if the customer asks you to. If the answer isn't in the facts,
say you don't know and suggest calling AEP.
Safety: never suggest touching or going near fallen lines; tell the customer to stay away
and report them to AEP. Never suggest running a generator indoors or in a garage.
Only mention calling 911 if the customer describes an emergency or danger to someone's
life or health.
If the customer writes in another language, answer in that language."""


@app.post("/chat")
def chat(req: ChatRequest):
    ans = get_answer(req.home_id, req.wind, req.crews)
    facts = {k: ans.get(k) for k in ["headline", "risk", "restoration", "facts", "estimates",
                                     "actions", "alert", "fallback"]}
    audit(req.home_id, "chat_question", req.question[:200])

    summary = " ".join(s.rstrip(".") + "." for s in [ans.get("headline") or ""] + ans.get("estimates", []) if s)
    fallback_answer = {"answer": "The chat assistant isn't available right now. Here's what we know: " + summary}

    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        return fallback_answer
    model = os.environ.get("GEMINI_MODEL", "gemini-flash-lite-latest")   # fast "lite" model
    try:
        r = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
            headers={"x-goog-api-key": key},          # key in a header, never in the URL
            json={
                "system_instruction": {"parts": [{"text": CHAT_RULES + "\n\nFACTS ABOUT THIS HOME (JSON):\n"
                                                  + json.dumps(facts)}]},
                "contents": [{"role": "user", "parts": [{"text": req.question}]}],
                "generationConfig": {"maxOutputTokens": 400, "temperature": 0.2},
            },
            timeout=30,
        )
        r.raise_for_status()
        # newer models can split an answer into parts; join them and skip "thinking" parts
        parts = r.json()["candidates"][0]["content"]["parts"]
        text = " ".join(p["text"].strip() for p in parts if p.get("text") and not p.get("thought"))
        if not text:
            raise ValueError("Gemini returned an empty answer")
        return {"answer": text}
    except Exception as e:
        # never crash the demo: log the problem and fall back to the template answer
        print("Gemini chat failed:", str(e)[:300])
        audit(req.home_id, "chat_fallback", type(e).__name__)
        return fallback_answer