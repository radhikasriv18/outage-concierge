"""
backtest.py - did our predictions match what really happened?

1. Home risk: for each storm, use a model that NEVER saw that storm (trained on the
   other two), predict every demo home, and compare with real damage on its power path.
2. Restoration: share of repairs finished within a day, simulated vs. AEP's real records.

Run after train_model.py:
    python backtest.py
Creates:
    cache/backtest.json   (shown by GET /backtest)
"""
from pathlib import Path
import json

import numpy as np
import pandas as pd
import geopandas as gpd
from sklearn.metrics import roc_auc_score

import engine
from build_training import STORMS, DATA
from train_model import load, make_models, NUMERIC, CATEGORY, LABEL

CACHE = Path(__file__).parent / "cache"


# ------------------------------------------------------------------ 1. home risk
def home_backtest(df, test_storm):
    """Train on the other storms, predict this one's homes, compare with reality."""
    train = df[df["storm"] != test_storm]
    test = df[df["storm"] == test_storm].set_index("location")
    model = make_models()["logistic_regression"]
    model.fit(train[NUMERIC + CATEGORY], train[LABEL])
    p_dev = pd.Series(model.predict_proba(test[NUMERIC + CATEGORY])[:, 1], index=test.index)
    damaged = test[LABEL]

    rows = []
    causes = set()      # distinct damaged devices that explain the "damaged" homes
    for home_id in engine.HOMES.index:
        locs = [s["location"] for s in engine.CHAINS.get(home_id, []) if s["location"] in p_dev.index]
        if not locs:
            continue
        p = 1 - np.prod([1 - p_dev[l] for l in locs])
        hit = [l for l in locs if damaged[l] == 1]
        if hit:
            causes.add(hit[-1])     # the most upstream damaged device on the path
        rows.append({"home_id": home_id, "predicted": p, "actual": int(bool(hit))})
    h = pd.DataFrame(rows)
    h["band"] = h["predicted"].map(engine.band_of)

    by_band = (h.groupby("band")
                 .agg(homes=("actual", "size"), predicted=("predicted", "mean"), actual=("actual", "mean"))
                 .reindex(["Low", "Medium", "High"]).dropna())
    return {
        "test_storm": test_storm,
        "homes": len(h),
        "average_predicted": round(float(h["predicted"].mean()), 3),
        "actual_share": round(float(h["actual"].mean()), 3),
        "home_roc_auc": round(float(roc_auc_score(h["actual"], h["predicted"])), 3)
                        if h["actual"].nunique() > 1 else None,
        # homes share upstream equipment, so the real number of independent events is small
        "independent_causes": len(causes),
        "by_band": [{"band": b, "homes": int(r.homes), "predicted": round(r.predicted, 3),
                     "actual": round(r.actual, 3)} for b, r in by_band.iterrows()],
    }


# ------------------------------------------------------------------ 2. restoration
def restoration_backtest(storm="feb2025"):
    """Share of repairs done within 1 day: simulation vs. AEP's real records."""
    start, end = STORMS[storm]
    d = gpd.read_file(DATA / "Data1" / "arcos_prod_damage_09_28_Clip.shp",
                      columns=["Report_Tim", "Repaired", "Repaired_D"], ignore_geometry=True)
    d["reported"] = pd.to_datetime(d["Report_Tim"])
    d = d[d["reported"].between(pd.Timestamp(start), pd.Timestamp(end) + pd.Timedelta(days=1))]
    d = d[d["Repaired"] == "Yes"]          # unrepaired rows have a fake export date
    days = (pd.to_datetime(d["Repaired_D"]) - d["reported"]).dt.days
    real_same_or_next_day = float((days <= 1).mean())

    # simulated: how long after the storm each repair job finishes, for different crew counts.
    # Report dates have no time of day, so "same or next day" in the records means up to ~48 hours.
    probs = engine.device_probabilities(engine.REAL_STORM_GUST)
    p = probs.reindex(engine._dev_ids).to_numpy()
    sweep = []
    for crews in range(1, 11):
        rng = np.random.default_rng(1)
        finishes = []
        for _ in range(200):
            finish, _, _ = engine._one_storm(p, crews, rng)
            finishes.extend(finish[finish > 0])
        finishes = np.array(finishes)
        sweep.append({"crews": crews,
                      "within_24h": round(float((finishes <= 24).mean()), 3),
                      "within_48h": round(float((finishes <= 48).mean()), 3),
                      "median_hours": round(float(np.median(finishes)), 1)})
    best = min(sweep, key=lambda s: abs(s["within_48h"] - real_same_or_next_day))
    current = next(s for s in sweep if s["crews"] == engine.DEFAULT_CREWS) \
        if engine.DEFAULT_CREWS <= 10 else None
    return {
        "storm": storm,
        "real_repairs": int(len(days)),
        "real_done_same_or_next_day": round(real_same_or_next_day, 3),
        "current_default_crews": engine.DEFAULT_CREWS,
        "current_within_48h": current["within_48h"] if current else None,
        "calibrated_crews": best["crews"],
        "calibrated_within_48h": best["within_48h"],
        "sweep": sweep,
        "note": "AEP's records only have dates, not times, so this is a day-level check. "
                "Calibrated crews = the crew count whose simulated repairs best match AEP's real "
                "Feb 2025 completion rate in this area.",
    }


def main():
    df = load()
    print("1. Home risk (each storm predicted by a model that never saw it)\n")
    risk = []
    for storm in STORMS:
        r = home_backtest(df, storm)
        risk.append(r)
        print(f"  {storm}: {r['homes']} homes | predicted avg {r['average_predicted']:.1%} "
              f"| actually damaged {r['actual_share']:.1%} | home ROC AUC {r['home_roc_auc']} "
              f"| only {r['independent_causes']} independent causes")
        for b in r["by_band"]:
            print(f"      {b['band']:6} {b['homes']:5} homes  predicted {b['predicted']:.1%}  actual {b['actual']:.1%}")

    print("\n2. Restoration time (Feb 2025)\n")
    rest = restoration_backtest()
    print(f"  real repairs done same or next day: {rest['real_done_same_or_next_day']:.0%} "
          f"(of {rest['real_repairs']})\n")
    print("  crews | simulated within 24 h | within 48 h | median")
    for s in rest["sweep"]:
        mark = "  <- best match to reality" if s["crews"] == rest["calibrated_crews"] else ""
        print(f"  {s['crews']:5} | {s['within_24h']:20.0%} | {s['within_48h']:10.0%} | "
              f"{s['median_hours']:5} h{mark}")
    print(f"\n  -> set DEFAULT_CREWS = {rest['calibrated_crews']} in engine.py "
          f"(currently {rest['current_default_crews']})")

    (CACHE / "backtest.json").write_text(json.dumps({"risk": risk, "restoration": rest}, indent=2))
    print("\nSaved cache/backtest.json")


if __name__ == "__main__":
    main()