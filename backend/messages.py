"""
messages.py - turns the engine's numbers into the words customers read.

Templates only (no AI here): every sentence is fixed, so numbers can never be
invented or changed. The AI chat uses these same sentences as its facts.

build_answer(home_id, gust, crews)  -> everything for the answer card (API.md /homes/{id})
alert_messages(home_id, gust, crews) -> the 4 alert messages (API.md /messages/{id})
"""
from datetime import datetime, timedelta
import json
from pathlib import Path

import engine

# demo replay: the real peak of the Feb 2025 storm in Roanoke (from the weather data)
STORM_PEAK = datetime(2025, 2, 16, 15, 0)
EQUIPMENT = json.loads((Path(__file__).parent / "cache" / "equipment.json").read_text())

HEADLINES = {
    "High": "Your power is at high risk of going out during this storm.",
    "Medium": "Your power might go out during this storm.",
    "Low": "Your power will most likely stay on during this storm.",
}


# ------------------------------------------------------------------ time in plain words
def clock(hours_after_peak):
    """3.5 -> 'Sun 6:30 PM' (day shown so overnight outages are clear)."""
    t = STORM_PEAK + timedelta(hours=hours_after_peak)
    minute = 0 if t.minute < 15 else 30 if t.minute < 45 else 0
    if t.minute >= 45:
        t += timedelta(hours=1)
    t = t.replace(minute=minute)
    return t.strftime("%a %I:%M %p").replace(" 0", " ").replace(":00", "")


def range_text(restore):
    if restore["min_hours"] is None:
        return None
    return f"{clock(restore['min_hours'])} – {clock(restore['max_hours'])}"


# ------------------------------------------------------------------ tips
def prep_actions(home, band, restore):
    """Preparation and safety steps, personalized. Safety items are marked."""
    actions = []
    if band == "Low":
        actions.append("Keep your phone charged in case conditions change")
        actions.append("SAFETY: Stay away from any fallen power lines and report them to AEP")
        return actions

    actions.append("Charge your phone and a backup battery now")
    actions.append("Keep a flashlight handy (avoid candles)")
    if home["life_support"] or home["medical_device"]:
        actions.append("Make sure your medical equipment's backup battery is fully charged, "
                       "and plan where you'd go if the outage lasts long")
    if home["has_sump_pump"]:
        actions.append("Your sump pump needs power: test its backup battery so your basement doesn't flood")
    if home["elderly_resident"]:
        actions.append("Check on older family members and plan to stay together if it gets cold")
    if home["works_from_home"]:
        actions.append("Download any files you'll need for work")
    long_outage = restore["max_hours"] is not None and restore["max_hours"] >= 8
    if long_outage:
        actions.append("Keep the fridge and freezer closed: food stays cold about 4 hours "
                       "in the fridge and about 48 hours in a full freezer")
    if home["has_generator"]:
        actions.append("SAFETY: Run your generator outside only, far from windows. "
                       "Never indoors or in a garage (carbon monoxide)")
    actions.append("SAFETY: Stay far away from fallen power lines, even if they look dead, "
                   "and report them to AEP")
    return actions


# ------------------------------------------------------------------ the full answer
def power_path_coords(home_id):
    """[lat, lon] pairs from the home up toward the substation."""
    home = engine.HOMES.loc[home_id]
    coords = [[round(float(home["lat"]), 6), round(float(home["lon"]), 6)]]
    for step in engine.CHAINS.get(home_id, []):
        e = EQUIPMENT.get(step["location"])
        if e:
            coords.append([round(e["lat"], 6), round(e["lon"], 6)])
    return coords


def build_answer(home_id, storm_gust_mph=engine.REAL_STORM_GUST, crews=engine.DEFAULT_CREWS):
    a = engine.assess_home(home_id, storm_gust_mph)
    if a is None:
        return None                     # unknown home -> the API returns 404
    home = engine.HOMES.loc[home_id]
    if a["fallback"]:
        return {"home_id": home_id, "fallback": a["fallback"],
                "actions": ["SAFETY: Stay far away from fallen power lines and report them to AEP"]}

    restore = engine.restoration(home_id, storm_gust_mph, crews)
    alert = engine.alert_plan(home_id, a, restore)
    band = a["band"]
    rt = range_text(restore)

    facts = [f"Storm scenario: wind gusts of about {round(storm_gust_mph)} mph in your area",
             f"Your power lines are {'above ground' if home['wire_type'] == 'Overhead' else 'underground' if home['wire_type'] == 'Underground' else 'of an unknown type'} (from AEP records)"]
    if home["life_support"]:
        facts.append("Your home is registered for life-support priority")

    estimates = [f"{band} chance of losing power (about {round(a['probability'] * 100)}%). "
                 f"{a['confidence']}."]
    if rt:
        estimates.append(f"If your power goes out, it should be back between {clock(restore['min_hours'])} and {clock(restore['max_hours'])}")
        estimates.append(f"Your repair would be about #{restore['queue_position']} in the crews' line")
    elif band != "Low":
        estimates.append("We can't give a reliable restoration time for your home in this scenario")

    return {
        "home_id": home_id,
        "headline": HEADLINES[band],
        "risk": {"band": band, "probability": a["probability"], "confidence": a["confidence"],
                 "doubts": a["doubts"], "reasons": a["reasons"]},
        "restoration": {"range_text": rt, "min_hours": restore["min_hours"],
                        "max_hours": restore["max_hours"], "queue_position": restore["queue_position"],
                        "what_changes_it": engine.what_changes_it(home_id, storm_gust_mph, crews)},
        "facts": facts,
        "estimates": estimates,
        "actions": prep_actions(home, band, restore),
        "alert": alert,
        "power_path": power_path_coords(home_id),
        "fallback": None,
        "profile_is_synthetic": True,
    }


# ------------------------------------------------------------------ the 4 alert messages
def alert_messages(home_id, storm_gust_mph=engine.REAL_STORM_GUST, crews=engine.DEFAULT_CREWS):
    """Short texts (they work even when the power and Wi-Fi are out)."""
    ans = build_answer(home_id, storm_gust_mph, crews)
    if ans is None or ans.get("fallback"):
        return []
    r = ans["restoration"]
    first_tip = next((t for t in ans["actions"] if not t.startswith("Charge")), ans["actions"][0])
    later = (r["max_hours"] or 0) + 3
    return [
        {"type": "pre_storm",
         "text": f"AEP: A strong storm arrives {clock(-6)}. {ans['headline']} "
                 f"Charge your phone now. Tip: {first_tip.replace('SAFETY: ', '')}. Reply HELP for more."},
        {"type": "outage_confirmed",
         "text": "AEP: Your power is out. Crews are on the way. " +
                 (f"Estimated back between {clock(r['min_hours'])} and {clock(r['max_hours'])}. "
                  if r["min_hours"] is not None else "We'll text you an estimate soon. ") +
                 "Stay away from fallen lines."},
        {"type": "estimate_updated",
         "text": f"AEP: Update: more damage was found on your line. New estimate: back by {clock(later)}. "
                 f"We're sorry for the delay."},
        {"type": "restored",
         "text": "AEP: Your power is back. If it's still out at your home, reply OUT or call AEP."},
    ]


if __name__ == "__main__":
    for h in ["606712043", "638817953", "333164148"]:
        print("=" * 70)
        print(json.dumps(build_answer(h), indent=2)[:2500])
    print("=" * 70)
    for m in alert_messages("606712043"):
        print(f"[{m['type']}] ({len(m['text'])} chars) {m['text']}")