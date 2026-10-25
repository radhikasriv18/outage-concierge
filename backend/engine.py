"""
engine.py - turns the trained model into answers for each home.

Part 1: load everything once (model, devices, homes, power paths)
Part 2: storm scenario -> damage probability for every device
Part 3: devices -> home outage probability, through the power path
Part 4: band, confidence, reasons in plain words
"""
from pathlib import Path
import json

import numpy as np
import pandas as pd
import joblib

CACHE = Path(__file__).parent / "cache"

# ------------------------------------------------------------------ PART 1: load once
_bundle = joblib.load(CACHE / "model.joblib")
MODEL = _bundle["models"]["logistic_regression"]   # won the unseen-storm test
FEATURES = _bundle["numeric"] + _bundle["category"]

# device facts come from the Feb 2025 table: pre-storm features + that storm's wind pattern
DEVICES = pd.read_csv(CACHE / "train_feb2025.csv", dtype={"location": str}).set_index("location")
DEVICES["homes_fed"] = np.log1p(DEVICES["homes_fed"])   # same transform as in training
# how much windier (or calmer) each spot was than average in the real storm
DEVICES["gust_offset"] = DEVICES["max_gust_mph"] - DEVICES["max_gust_mph"].mean()
REAL_STORM_GUST = round(float(DEVICES["max_gust_mph"].mean()), 1)

HOMES = pd.read_csv(CACHE / "homes.csv", dtype={"home_id": str, "circuit_id": str}).set_index("home_id")
CHAINS = json.loads((CACHE / "chains.json").read_text())

# risk bands for the chance a home loses power
HIGH, MEDIUM = 0.30, 0.10      # 30%+ = High, 10-30% = Medium, under 10% = Low

def kind_words(kind):
    """Plain words for equipment names used in the power-path file."""
    if kind == "Distribution":
        return "the transformer near your home"
    if kind.startswith("Fuse"):
        return "a safety fuse on your street's line"
    if kind.startswith("Recloser") or kind == "Sectionalizer":
        return "a larger safety switch on your neighborhood line"
    if kind == "Step":
        return "a voltage transformer on your neighborhood line"
    return "equipment on your line"


# ------------------------------------------------------------------ PART 2: device probabilities
def device_probabilities(storm_gust_mph=REAL_STORM_GUST):
    """Chance each device gets damaged if the storm's average gust is `storm_gust_mph`."""
    X = DEVICES.copy()
    X["max_gust_mph"] = storm_gust_mph + X["gust_offset"]   # keep each spot's local pattern
    p = MODEL.predict_proba(X[FEATURES])[:, 1]
    return pd.Series(p, index=DEVICES.index)


# ------------------------------------------------------------------ PART 3: home probability
def home_probability(home_id, probs):
    """P(home out) = 1 - product of (1 - p) over the devices on its power path."""
    chain = CHAINS.get(home_id, [])
    path = [(step["location"], step["kind"]) for step in chain]
    known = [(loc, kind, float(probs[loc])) for loc, kind in path if loc in probs.index]
    if not known:
        return None, path, known
    survive = np.prod([1 - p for _, _, p in known])
    return float(1 - survive), path, known


# ------------------------------------------------------------------ PART 4: band, confidence, reasons
def band_of(p):
    return "High" if p >= HIGH else "Medium" if p >= MEDIUM else "Low"


def confidence(p, path, known):
    doubts = []
    if len(known) < len(path) - 1:          # the main breaker (last item) has no device row
        doubts.append("We're missing details for some equipment that feeds your home")
    if abs(p - HIGH) < 0.05 or abs(p - MEDIUM) < 0.03:
        doubts.append("Your home is close to the line between two risk levels")
    # the model itself is only moderately accurate on storms it hasn't seen (ROC AUC ~0.62),
    # so the best we ever claim is "Fairly sure"
    level = ["Fairly sure", "Somewhat sure", "Not sure"][min(len(doubts), 2)]
    return level, doubts


def reasons_for(home_id, p, known, storm_gust_mph):
    home = HOMES.loc[home_id]
    band = band_of(p)
    reasons = []
    if band == "Low":
        reasons.append(f"Winds near you are expected to stay around {round(storm_gust_mph)} mph or less")
        if home["wire_type"] == "Underground":
            reasons.append("Your power lines are underground, away from wind and trees")
        return reasons
    reasons.append(f"Strong wind gusts of about {round(storm_gust_mph)} mph are expected")
    weakest = max(known, key=lambda k: k[2])
    reasons.append(f"The most at-risk part of your power path is {kind_words(weakest[1])}")
    if home["wire_type"] == "Overhead":
        reasons.append("Your power lines are above ground, where wind and trees can reach them")
    if len(known) >= 5:
        reasons.append(f"Your power passes through {len(known)} pieces of equipment, and any one can fail")
    return reasons[:3]


def assess_home(home_id, storm_gust_mph=REAL_STORM_GUST, probs=None):
    """Everything about one home's outage risk for a storm scenario."""
    if home_id not in HOMES.index:
        return None
    if probs is None:
        probs = device_probabilities(storm_gust_mph)
    p, path, known = home_probability(home_id, probs)
    if p is None:
        return {"home_id": home_id, "fallback": "We can't predict this home reliably right now, "
                "because we don't have details about the equipment that feeds it."}
    level, doubts = confidence(p, path, known)
    return {
        "home_id": home_id,
        "probability": round(p, 3),
        "band": band_of(p),
        "confidence": level,
        "doubts": doubts,
        "reasons": reasons_for(home_id, p, known, storm_gust_mph),
        "path": [{"location": loc, "kind": kind, "probability": round(pr, 3)} for loc, kind, pr in known],
        "fallback": None,
    }


def assess_all(storm_gust_mph=REAL_STORM_GUST):
    """Band for every demo home (for the map)."""
    probs = device_probabilities(storm_gust_mph)
    rows = []
    for home_id in HOMES.index:
        p, _, _ = home_probability(home_id, probs)
        rows.append({"home_id": home_id, "probability": p,
                     "band": band_of(p) if p is not None else "Unknown"})
    return pd.DataFrame(rows)


# ------------------------------------------------------------------ PART 5: restoration simulation
LABOR = json.loads((CACHE / "labor.json").read_text())
# the real mix of damage types in AEP's records (all 1,659 damage records)
DAMAGE_MIX = {"primary": 704, "Pole": 355, "Fuse Bank": 280, "secondary": 156,
              "Transformer": 74, "Recloser Bank": 58, "Switch": 19, "default": 13}
_mix_kinds = list(DAMAGE_MIX)
_mix_p = np.array(list(DAMAGE_MIX.values()), dtype=float) / sum(DAMAGE_MIX.values())
_mix_hours = np.array([LABOR["hours_by_asset"][k] for k in _mix_kinds])

DEFAULT_CREWS = 10        # ASSUMPTION: crews assigned to this area (confirm with AEP)
# ASSUMPTION (confirm with AEP): the Excel hours are PERSON-hours and a crew has 3 people.
# Evidence: half of AEP's real repairs finished the same day, which only fits if a
# 23-hour pole job (5.2 h x 4.5) is shared by a crew. Set CREW_SIZE = 1 if they're crew-hours.
CREW_SIZE = 3
START_DELAY_HOURS = 2     # ASSUMPTION: time to assess damage before repairs start
RUNS = 300                # how many random storms we simulate

# power paths as a table: one row per home, one column per step (-1 = no step)
_home_ids = list(HOMES.index)
_dev_ids = sorted({s["location"] for h in _home_ids for s in CHAINS.get(h, [])
                   if s["location"] in DEVICES.index})
_dev_index = {d: i for i, d in enumerate(_dev_ids)}
_max_len = max(len(CHAINS.get(h, [])) for h in _home_ids)
PATHS = np.full((len(_home_ids), _max_len), -1)
for r, h in enumerate(_home_ids):
    idx = [_dev_index[s["location"]] for s in CHAINS.get(h, []) if s["location"] in _dev_index]
    PATHS[r, :len(idx)] = idx
# homes each device feeds (inside the demo area), and life-support homes it feeds
_feeds = np.zeros(len(_dev_ids))
_feeds_life = np.zeros(len(_dev_ids))
_life = HOMES["life_support"].astype(bool).to_numpy()
for r in range(len(_home_ids)):
    for d in PATHS[r][PATHS[r] >= 0]:
        _feeds[d] += 1
        _feeds_life[d] += _life[r]


def _one_storm(p_dev, crews, rng):
    """One random storm: which devices fail, the repair order, and when each home is back."""
    failed = np.flatnonzero(rng.random(len(p_dev)) < p_dev)
    finish = np.zeros(len(p_dev))                      # 0 = not damaged
    if len(failed) == 0:
        return finish, np.zeros(len(_home_ids)), {}
    # size of each job: a damage type drawn from AEP's real mix, x 4.5 for travel/setup,
    # with +-30% random variation
    kinds = rng.choice(len(_mix_kinds), size=len(failed), p=_mix_p)
    hours = (_mix_hours[kinds] * LABOR["indirect_multiplier"] / CREW_SIZE
             * rng.lognormal(0, 0.3, len(failed)))
    # priority: life-support homes first, then the most homes restored per hour of work
    priority = _feeds_life[failed] * 1000 + _feeds[failed] / hours
    order = np.argsort(-priority)
    crew_free = np.full(crews, float(START_DELAY_HOURS))  # when each crew is next available
    queue_pos = {}
    for pos, j in enumerate(order, start=1):
        c = np.argmin(crew_free)                       # the next free crew takes the job
        crew_free[c] += hours[j]
        finish[failed[j]] = crew_free[c]
        queue_pos[failed[j]] = pos
    # a home is back when the LAST broken device on its path is fixed
    padded = np.append(finish, 0)                      # index -1 -> 0
    home_back = padded[PATHS].max(axis=1)
    return finish, home_back, queue_pos


_sim_cache = {}


def simulate(storm_gust_mph=REAL_STORM_GUST, crews=DEFAULT_CREWS):
    """Run many random storms. Returns per-home restoration hours (NaN = power stayed on)."""
    key = (round(storm_gust_mph, 1), crews)
    if key in _sim_cache:
        return _sim_cache[key]
    probs = device_probabilities(storm_gust_mph)
    p_dev = probs.reindex(_dev_ids).to_numpy()
    rng = np.random.default_rng(0)                     # same answer every time for the same inputs
    back = np.full((RUNS, len(_home_ids)), np.nan)
    queue = np.full((RUNS, len(_home_ids)), np.nan)
    for r in range(RUNS):
        finish, home_back, queue_pos = _one_storm(p_dev, crews, rng)
        out = home_back > 0
        back[r, out] = home_back[out]
        if queue_pos:
            # the home's place in line = position of the last job its power waits for
            for h in np.flatnonzero(out):
                devs = PATHS[h][PATHS[h] >= 0]
                last = devs[np.argmax(finish[devs])]
                queue[r, h] = queue_pos[last]
    _sim_cache[key] = (back, queue)
    return back, queue


def restoration(home_id, storm_gust_mph=REAL_STORM_GUST, crews=DEFAULT_CREWS):
    """If this home loses power: likely hours until it's back, and its place in line."""
    back, queue = simulate(storm_gust_mph, crews)
    h = _home_ids.index(home_id)
    hours = back[:, h][~np.isnan(back[:, h])]
    if len(hours) < 10:          # it almost never loses power in the simulations
        return {"outage_runs": int(len(hours)), "min_hours": None, "max_hours": None,
                "typical_hours": None, "queue_position": None}
    q = queue[:, h][~np.isnan(queue[:, h])]
    return {
        "outage_runs": int(len(hours)),
        "min_hours": round(float(np.percentile(hours, 10)), 1),     # 10th percentile
        "typical_hours": round(float(np.median(hours)), 1),
        "max_hours": round(float(np.percentile(hours, 90)), 1),     # 90th percentile
        "queue_position": int(np.median(q)),
    }


def what_changes_it(home_id, storm_gust_mph=REAL_STORM_GUST, crews=DEFAULT_CREWS):
    """Re-run with one thing changed, so customers see what moves their estimate."""
    out = []
    now = restoration(home_id, storm_gust_mph, crews)
    more = restoration(home_id, storm_gust_mph, crews + 5)
    if now["max_hours"] and more["max_hours"]:
        if now["max_hours"] - more["max_hours"] >= 1:
            out.append(f"If 5 more crews arrive: about {round(more['min_hours'])} to "
                       f"{round(more['max_hours'])} hours")
        else:
            out.append("Your repair is near the front of the line, so more crews "
                       "wouldn't change your time much")
    # wind changes the CHANCE of losing power (time estimates get unreliable when
    # outages become rare, so we don't compare those)
    a_now = assess_home(home_id, storm_gust_mph)
    a_weak = assess_home(home_id, storm_gust_mph - 10)
    if a_now["probability"] is not None:
        out.append(f"If winds are 10 mph weaker: your chance of losing power drops from "
                   f"{a_now['probability']:.0%} to {a_weak['probability']:.0%}")
    return out


# ------------------------------------------------------------------ PART 6: neighbor comparison
def nearest_neighbor(home_id, different_path=True):
    """The closest demo home, by default one whose power path is different."""
    me = HOMES.loc[home_id]
    d = (HOMES["lat"] - me["lat"]) ** 2 + (HOMES["lon"] - me["lon"]) ** 2
    my_path = [s["location"] for s in CHAINS.get(home_id, [])]
    for other in d.sort_values().index:
        if other == home_id:
            continue
        other_path = [s["location"] for s in CHAINS.get(other, [])]
        if not different_path or other_path != my_path:
            return other
    return None


def compare_neighbors(home_id, neighbor_id, storm_gust_mph=REAL_STORM_GUST):
    """Why one home might lose power while the neighbor keeps it."""
    probs = device_probabilities(storm_gust_mph)
    mine = {s["location"]: s["kind"] for s in CHAINS.get(home_id, [])}
    theirs = {s["location"]: s["kind"] for s in CHAINS.get(neighbor_id, [])}
    shared = [loc for loc in mine if loc in theirs]
    only_mine = [loc for loc in mine if loc not in theirs and loc in probs.index]
    only_theirs = [loc for loc in theirs if loc not in mine and loc in probs.index]

    p_me = home_probability(home_id, probs)[0]
    p_them = home_probability(neighbor_id, probs)[0]

    if not only_mine and not only_theirs:
        text = ("You and your neighbor get power through exactly the same equipment, "
                "so you'll almost always lose and regain power together.")
    else:
        parts = []
        if only_mine:
            weakest = max(only_mine, key=lambda l: probs[l])
            kind = mine[weakest]
            short = ("transformers" if kind == "Distribution" else
                     "safety fuses" if kind.startswith("Fuse") else
                     "safety switches" if kind.startswith("Recloser") else "pieces of equipment")
            parts.append(f"You and your neighbor are on different {short}")
        if shared:
            parts.append(f"you share the bigger equipment upstream ({len(shared)} pieces)")
        text = ", and ".join(parts) + ". "
        if p_me is not None and p_them is not None:
            if p_me > p_them + 0.02:
                text += "Your branch has the weaker equipment, which is why your risk is higher than theirs."
            elif p_them > p_me + 0.02:
                text += "Their branch has the weaker equipment, so they're more likely to lose power than you."
            else:
                text += "Your chances are about the same."
        text += (" If only one of you loses power, the problem is on that home's own branch, "
                 "not the shared line.")
    return {
        "home": home_id, "neighbor": neighbor_id,
        "same_line": not only_mine and not only_theirs,
        "shared_equipment": len(shared),
        "my_probability": None if p_me is None else round(p_me, 3),
        "neighbor_probability": None if p_them is None else round(p_them, 3),
        "explanation": text,
    }


# ------------------------------------------------------------------ PART 7: alerts and escalation
ALERT_RULES = [
    "High risk: text 12 hours before the storm",
    "Medium risk + medical device, life support or elderly resident: text 12 hours before",
    "Medium risk, everyone else: text 6 hours before",
    "Life support: phone call + text 24 hours before",
    "Low risk: no alert (avoids alert fatigue)",
]
ESCALATION_RULES = [
    "Life support + Medium or High risk: add to AEP's welfare-check list before the storm",
    "Medical device or elderly resident + outage could last over 24 hours: call to check on them",
    "High risk but 'Not sure': a person at AEP reviews the prediction",
    "Restoration estimate slips by more than 4 hours: notify a supervisor",
]


def alert_plan(home_id, assessment, restore):
    """Should this home get an alert, how, when, and should a person at AEP be told?"""
    home = HOMES.loc[home_id]
    band = assessment.get("band")
    life = bool(home["life_support"])
    vulnerable = life or bool(home["medical_device"]) or bool(home["elderly_resident"])

    eligible, channel, timing, reason = False, None, None, "Low risk: no alert needed"
    if life and band in ("Medium", "High"):
        eligible, channel, timing = True, "Phone call and text message", "24 hours before the storm"
        reason = "Life-support customer with elevated risk"
    elif band == "High":
        eligible, channel, timing = True, "Text message", "12 hours before the storm"
        reason = "High risk of losing power"
    elif band == "Medium" and vulnerable:
        eligible, channel, timing = True, "Text message", "12 hours before the storm"
        reason = "Medium risk, and someone at home may need extra time to prepare"
    elif band == "Medium":
        eligible, channel, timing = True, "Text message", "6 hours before the storm"
        reason = "Medium risk of losing power"

    escalate, escalate_reasons = False, []
    if life and band in ("Medium", "High"):
        escalate_reasons.append("Add to the welfare-check list before the storm")
    long_outage = restore.get("max_hours") is not None and restore["max_hours"] > 24
    if (bool(home["medical_device"]) or bool(home["elderly_resident"])) and long_outage:
        escalate_reasons.append("Vulnerable household and the outage could last over a day")
    if band == "High" and assessment.get("confidence") == "Not sure":
        escalate_reasons.append("High-risk prediction with low confidence: needs a person to review")
    escalate = bool(escalate_reasons)

    return {"eligible": eligible, "channel": channel, "timing": timing, "reason": reason,
            "escalate": escalate, "escalate_reasons": escalate_reasons}


def estimate_slipped(old_max_hours, new_max_hours):
    """Escalation rule 4: the estimate got more than 4 hours worse."""
    return (old_max_hours is not None and new_max_hours is not None
            and new_max_hours - old_max_hours > 4)


if __name__ == "__main__":
    print("Real Feb 2025 storm, average gust:", REAL_STORM_GUST, "mph\n")
    for gust in [30, 45, REAL_STORM_GUST, 70]:
        a = assess_all(gust)
        print(f"{gust:>5} mph -> {a['band'].value_counts().to_dict()}  "
              f"(median chance {a['probability'].median():.0%})")
    print()
    example = "606712043"
    r = assess_home(example)
    print(json.dumps({k: r[k] for k in ["probability", "band", "confidence"]}))

    import time
    t0 = time.time()
    print("\nRestoration (if the power goes out):", restoration(example))
    print(f"(simulated {RUNS} storms in {time.time() - t0:.1f} s)")
    print("What changes it:", what_changes_it(example))
    for crews in [5, 10, 20]:
        print(f"{crews:>3} crews ->", restoration(example, crews=crews))