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


if __name__ == "__main__":
    print("Real Feb 2025 storm, average gust:", REAL_STORM_GUST, "mph\n")
    for gust in [30, 45, REAL_STORM_GUST, 70]:
        a = assess_all(gust)
        print(f"{gust:>5} mph -> {a['band'].value_counts().to_dict()}  "
              f"(median chance {a['probability'].median():.0%})")
    print()
    example = "606712043"
    r = assess_home(example)
    print(json.dumps(r, indent=2))