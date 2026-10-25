"""
add_weather.py - add real storm weather to each training table.

Open-Meteo's historical weather is a grid (~10 km). We split the area into
0.1-degree squares, download each square's max wind gust and total rain for
each storm, and give every device the values of its square.

Run after build_training.py:
    python add_weather.py
Updates:
    cache/train_<storm>.csv   (adds max_gust_mph, rain_in)
    cache/weather_grid.csv    (the downloaded values, for checking)
"""
from pathlib import Path
import time

import pandas as pd
import requests

from build_training import STORMS

CACHE = Path(__file__).parent / "cache"
GRID = 0.1           # degrees, about 10 km
BATCH = 50           # squares per request
URL = "https://archive-api.open-meteo.com/v1/archive"


def to_square(values):
    """Center of the 0.1-degree square each value falls in."""
    return ((values / GRID).round() * GRID).round(2)


def fetch(squares, start, end):
    """Max gust (mph) and total rain (inches) for each square during a storm."""
    rows = []
    for i in range(0, len(squares), BATCH):
        batch = squares.iloc[i:i + BATCH]
        params = {
            "latitude": ",".join(map(str, batch["sq_lat"])),
            "longitude": ",".join(map(str, batch["sq_lon"])),
            "start_date": start, "end_date": end,
            "daily": "wind_gusts_10m_max,precipitation_sum",
            "wind_speed_unit": "mph", "precipitation_unit": "inch",
            "timezone": "America/New_York",
        }
        r = requests.get(URL, params=params, timeout=60)
        if r.status_code != 200:
            raise RuntimeError(f"Open-Meteo said {r.status_code}: {r.text[:300]}")
        data = r.json()
        if isinstance(data, dict):        # one location comes back as a dict, many as a list
            data = [data]
        for (_, sq), d in zip(batch.iterrows(), data):
            gusts = [g for g in d["daily"]["wind_gusts_10m_max"] if g is not None]
            rain = [p for p in d["daily"]["precipitation_sum"] if p is not None]
            rows.append({
                "sq_lat": sq["sq_lat"], "sq_lon": sq["sq_lon"],
                "max_gust_mph": round(max(gusts), 1) if gusts else None,
                "rain_in": round(sum(rain), 2) if rain else None,
            })
        time.sleep(1)   # be polite to the free service
    return pd.DataFrame(rows)


def main():
    all_weather = []
    for name, (start, end) in STORMS.items():
        path = CACHE / f"train_{name}.csv"
        t = pd.read_csv(path, dtype={"location": str})
        t = t.drop(columns=["max_gust_mph", "rain_in"], errors="ignore")   # safe to re-run
        t["sq_lat"], t["sq_lon"] = to_square(t["lat"]), to_square(t["lon"])
        squares = t[["sq_lat", "sq_lon"]].drop_duplicates().reset_index(drop=True)

        print(f"{name}: downloading weather for {len(squares)} squares...")
        w = fetch(squares, start, end)
        w["storm"] = name
        all_weather.append(w)

        t = t.merge(w.drop(columns="storm"), on=["sq_lat", "sq_lon"], how="left")
        t.drop(columns=["sq_lat", "sq_lon"]).to_csv(path, index=False)
        print(f"   gusts {w['max_gust_mph'].min()}-{w['max_gust_mph'].max()} mph, "
              f"rain {w['rain_in'].min()}-{w['rain_in'].max()} in, "
              f"missing for {t['max_gust_mph'].isna().sum()} devices")

    pd.concat(all_weather).to_csv(CACHE / "weather_grid.csv", index=False)
    print("Done.")


if __name__ == "__main__":
    main()