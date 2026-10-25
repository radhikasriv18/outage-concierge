def wind_points(gust_mph):
    if gust_mph < 30:
        return 0
    elif gust_mph < 46:
        return 1
    elif gust_mph < 58:
        return 3
    else:
        return 5


def wind_factor(gust_mph):
    if gust_mph < 30:
        return 0
    elif gust_mph < 46:
        return 0.5
    elif gust_mph < 58:
        return 1
    else:
        return 1.5


def risk_score(home, gust_mph):
    """Returns (band, score, reasons) for one home."""
    weak = []   # list of (points, reason in plain words)

    if home["wire_type"] == "Overhead":
        weak.append((2, "Your power lines are above ground, where wind and trees can reach them"))
    if home["damaged_on_chain"] > 0:
        weak.append((3 * min(home["damaged_on_chain"], 2),
                     "Equipment that feeds your home was damaged in past storms"))
    if home["nearby_damage_storm"] > 0:
        weak.append((min(home["nearby_damage_storm"], 3),
                     "There was storm damage close to your home before"))
    if home["circuit_damage_history"] > 5:
        weak.append((1, "Your neighborhood line has broken often in other storms"))
    if home["chain_length"] >= 6:
        weak.append((1, "Your power passes through many pieces of equipment"))

    weak_points = sum(p for p, _ in weak)
    score = wind_points(gust_mph) + weak_points * wind_factor(gust_mph)

    if score >= 8:
        band = "High"
    elif score >= 5:
        band = "Medium"
    else:
        band = "Low"

    reasons = []
    if band == "Low":
        if wind_factor(gust_mph) == 0:
            reasons.append(f"Winds are expected to stay calm (about {round(gust_mph)} mph)")
        if not weak:
            reasons.append("Your home has no known weak spots on its power path")
        elif wind_factor(gust_mph) > 0:
            reasons.append("The wind isn't strong enough to cause much damage near you")
    else:
        if wind_points(gust_mph) >= 3:
            reasons.append(f"Strong wind gusts of about {round(gust_mph)} mph are expected")
        weak.sort(reverse=True)
        reasons += [r for _, r in weak]
    return band, float(round(score, 1)), reasons[:3]
if __name__ == "__main__":
    import pandas as pd
    homes = pd.read_csv("cache/homes.csv", dtype={"home_id": str})
    home = homes[homes["home_id"] == "606712043"].iloc[0]
    for w in [20, 40, 55, 70]:
        print(w, "mph ->", risk_score(home, w))