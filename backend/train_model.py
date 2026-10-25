"""
train_model.py - train and test the equipment damage model.

Test method: "leave one storm out". Train on two storms, test on the third,
three times. Each test is a storm the model has never seen.

Run after add_weather.py:
    python train_model.py
Creates:
    cache/model.joblib          the chosen model, trained on all three storms
    cache/model_report.json     test scores (for the backtest page and judges)
    cache/feature_weights.csv   what the model learned (logistic regression)
"""
from pathlib import Path
import json

import numpy as np
import pandas as pd
import joblib
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score, average_precision_score, brier_score_loss
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from build_training import STORMS

CACHE = Path(__file__).parent / "cache"

NUMERIC = [
    "max_gust_mph",                         # weather at the device
    "overhead", "install_year",                        # the device itself
    "homes_fed", "devices_upstream",                   # its place in the network
    "poles_nearby", "share_wood_poles", "avg_pole_height_ft",
    "share_weak_class_poles", "avg_pole_year",         # poles around it
    "overhead_line_m", "near_backbone",                # lines around it
    "past_damage_400m",                                # history before the storm
]
CATEGORY = ["kind"]
LABEL = "label_damaged"


def load():
    parts = [pd.read_csv(CACHE / f"train_{name}.csv", dtype={"location": str}) for name in STORMS]
    df = pd.concat(parts, ignore_index=True)
    df["homes_fed"] = np.log1p(df["homes_fed"])   # 1 vs 2,800 homes: use log scale
    return df


def make_models():
    # missing values: fill with the median and add a "was missing" flag
    numeric = Pipeline([("fill", SimpleImputer(strategy="median", add_indicator=True)),
                        ("scale", StandardScaler())])
    prep = ColumnTransformer([("num", numeric, NUMERIC),
                              ("cat", OneHotEncoder(handle_unknown="ignore"), CATEGORY)])
    return {
        "logistic_regression": Pipeline([("prep", prep),
                                         ("model", LogisticRegression(max_iter=2000, C=0.5))]),
        "gradient_boosting": Pipeline([("prep", ColumnTransformer(
                                           [("num", "passthrough", NUMERIC),
                                            ("cat", OneHotEncoder(handle_unknown="ignore"), CATEGORY)])),
                                       ("model", HistGradientBoostingClassifier(
                                           max_iter=200, learning_rate=0.05, max_leaf_nodes=15,
                                           min_samples_leaf=50, random_state=0))]),
    }


def lift_top10(y, p):
    """How many times more damage in the riskiest 10% than on average."""
    cut = np.quantile(p, 0.9)
    return float(y[p >= cut].mean() / y.mean()) if y.mean() > 0 else None


def main():
    df = load()
    X, y = df[NUMERIC + CATEGORY], df[LABEL]
    results = []

    print("Leave-one-storm-out test (each row = a storm the model never saw)\n")
    print(f"{'model':22} {'test storm':10} {'damaged':>8} {'ROC AUC':>8} {'top-10% lift':>13}")
    for name, model in make_models().items():
        for test_storm in STORMS:
            train = df["storm"] != test_storm
            model.fit(X[train], y[train])
            p = model.predict_proba(X[~train])[:, 1]
            yt = y[~train].to_numpy()
            r = {
                "model": name, "test_storm": test_storm,
                "damaged_share": round(float(yt.mean()), 4),
                "roc_auc": round(float(roc_auc_score(yt, p)), 3),
                "avg_precision": round(float(average_precision_score(yt, p)), 3),
                "brier": round(float(brier_score_loss(yt, p)), 4),
                "lift_top10": round(lift_top10(yt, p), 2),
            }
            results.append(r)
            print(f"{name:22} {test_storm:10} {r['damaged_share']:>8.1%} {r['roc_auc']:>8} {r['lift_top10']:>12}x")

    res = pd.DataFrame(results)
    summary = res.groupby("model")[["roc_auc", "avg_precision", "lift_top10"]].mean().round(3)
    print("\nAverage over the three test storms:")
    print(summary.to_string())

    best = summary["roc_auc"].idxmax()
    print(f"\nBest on unseen storms: {best}")

    # final models: train on all three storms
    models = make_models()
    for m in models.values():
        m.fit(X, y)
    joblib.dump({"models": models, "chosen": best, "numeric": NUMERIC, "category": CATEGORY},
                CACHE / "model.joblib")

    # what logistic regression learned (positive = raises risk)
    lr = models["logistic_regression"]
    names = lr.named_steps["prep"].get_feature_names_out()
    weights = pd.DataFrame({"feature": names, "weight": lr.named_steps["model"].coef_[0]})
    weights = weights.reindex(weights["weight"].abs().sort_values(ascending=False).index)
    weights.to_csv(CACHE / "feature_weights.csv", index=False)
    print("\nWhat logistic regression learned (bigger = stronger effect, + raises risk):")
    print(weights.head(12).round(3).to_string(index=False))

    (CACHE / "model_report.json").write_text(json.dumps({
        "method": "leave-one-storm-out",
        "results": results,
        "average": summary.reset_index().to_dict("records"),
        "chosen_model": best,
    }, indent=2))
    print("\nSaved cache/model.joblib, cache/model_report.json, cache/feature_weights.csv")


if __name__ == "__main__":
    main()