"""
build_training.py - build the machine-learning table.

One row = one piece of equipment on a power path, for one storm.
Features use only information from BEFORE the storm. The label is from DURING it.

Run:
    python build_training.py
Creates:
    cache/train_<storm>.csv   for each storm
"""
from pathlib import Path
from collections import defaultdict

import numpy as np
import pandas as pd
import geopandas as gpd

BACKEND = Path(__file__).parent
DATA = BACKEND.parent / "aep_data" / "data" / "extracted"
CACHE = BACKEND / "cache"
METERS = "EPSG:32617"   # map projection in meters

STORMS = {
    "feb2025": ("2025-02-12", "2025-02-18"),   # 1,254 damage records -> training
    "sep2024": ("2024-09-26", "2024-10-02"),   #   194 damage records -> testing
    "jan2025": ("2025-01-06", "2025-01-07"),   #    46 damage records -> extra test
}
LABEL_RADIUS = 75       # damage within 75 m of the equipment = "damaged"
SURROUND_RADIUS = 100   # look at poles and lines within 100 m
HISTORY_RADIUS = 400    # past damage within 400 m


# ------------------------------------------------------------------ PART 1: equipment
def load_equipment():
    """All transformers, fuses, reclosers and switches, with basic facts."""
    t = gpd.read_file(DATA / "Data2" / "Transformer_Clip.shp",
                      columns=["location_n", "structure_", "a_phase_da", "aep_custom"])
    t["kind"] = "Transformer"
    t["overhead"] = t["structure_"].str.startswith("Pole")
    t["install_year"] = pd.to_datetime(t["a_phase_da"], errors="coerce").dt.year

    f = gpd.read_file(DATA / "Data1" / "Fuse_Bank_Clip.shp",
                      columns=["location_n", "mounting", "aep_custom"])
    f["kind"] = "Fuse"
    f["overhead"] = f["mounting"] == "Overhead"

    r = gpd.read_file(DATA / "Data2" / "Recloser_Bank_Clip.shp",
                      columns=["location_n", "aep_custom"])
    r["kind"] = "Recloser"
    r["overhead"] = True

    s = gpd.read_file(DATA / "Data2" / "Switch_Clip.shp",
                      columns=["location_n", "aep_custom"])
    s["kind"] = "Switch"
    s["overhead"] = True

    cols = ["location_n", "kind", "overhead", "install_year", "geometry"]
    eq = pd.concat([x.reindex(columns=cols) for x in (t, f, r, s)], ignore_index=True)
    eq = gpd.GeoDataFrame(eq, geometry="geometry", crs=t.crs).to_crs(METERS)
    eq = eq.rename(columns={"location_n": "location"}).dropna(subset=["location"])
    eq = eq.drop_duplicates("location")
    eq["overhead"] = eq["overhead"].fillna(False).astype(int)
    return eq


# ------------------------------------------------------------------ PART 2: network position
def network_features():
    """From the topology file: how deep each device sits, and how many homes it feeds."""
    homes_fed = defaultdict(int)
    depth = {}
    with open(DATA / "matched_upstream" / "matched_upstream.txt") as fh:
        for line in fh:
            items = line.strip().split("\t")[1:]
            locations = [it.split("*")[3] for it in items]
            n = len(locations)
            for i, loc in enumerate(locations):
                homes_fed[loc] += 1
                # devices between this one and the main breaker (last item)
                d = n - 1 - i
                depth[loc] = min(depth.get(loc, d), d)
    return pd.DataFrame({"location": list(homes_fed),
                         "homes_fed": list(homes_fed.values()),
                         "devices_upstream": [depth[k] for k in homes_fed]})


# ------------------------------------------------------------------ PART 3: surroundings
def surroundings(eq):
    """Poles and power lines within 100 m of each device."""
    zone = eq[["location", "geometry"]].copy()
    zone["geometry"] = zone.buffer(SURROUND_RADIUS)

    poles = gpd.read_file(DATA / "Data1" / "Pole_Clip.shp",
                          columns=["material", "height", "class", "date_insta"]).to_crs(METERS)
    poles["wood"] = poles["material"].isin(["Pine", "Wood"]).astype(int)
    poles["height_ft"] = pd.to_numeric(poles["height"].str.extract(r"(\d+)")[0], errors="coerce")
    # pole class: lower number = stronger pole; 5 and above are the lighter classes
    poles["weak_class"] = (pd.to_numeric(poles["class"], errors="coerce") >= 5).astype(int)
    poles["year"] = pd.to_datetime(poles["date_insta"], errors="coerce").dt.year
    j = gpd.sjoin(poles, zone, predicate="within")
    p = j.groupby("location").agg(
        poles_nearby=("wood", "size"),
        share_wood_poles=("wood", "mean"),
        avg_pole_height_ft=("height_ft", "mean"),
        share_weak_class_poles=("weak_class", "mean"),
        avg_pole_year=("year", "mean"),
    )

    lines = gpd.read_file(DATA / "Data1" / "Primary_ExportFeatures.shp",
                          columns=["mounting", "usage"]).to_crs(METERS)
    lines["length_m"] = lines.length
    lines["overhead_m"] = lines["length_m"] * (lines["mounting"] == "Overhead")
    lines["backbone"] = (lines["usage"] == "Backbone").astype(int)
    j = gpd.sjoin(lines, zone, predicate="intersects")
    l = j.groupby("location").agg(
        overhead_line_m=("overhead_m", "sum"),
        near_backbone=("backbone", "max"),
    )
    return p.join(l, how="outer").reset_index()


# ------------------------------------------------------------------ PART 4: damage history + label
def load_damage():
    d = gpd.read_file(DATA / "Data1" / "arcos_prod_damage_09_28_Clip.shp",
                      columns=["Report_Tim"]).to_crs(METERS)
    d["reported"] = pd.to_datetime(d["Report_Tim"])
    return d[["reported", "geometry"]]


def count_within(eq, points, radius):
    """For each device, how many points are within `radius` meters."""
    if points.empty:
        return pd.Series(0, index=eq["location"])
    zone = eq[["location", "geometry"]].copy()
    zone["geometry"] = zone.buffer(radius)
    j = gpd.sjoin(points[["geometry"]], zone, predicate="within")
    return j.groupby("location").size().reindex(eq["location"]).fillna(0).astype(int)


def storm_table(eq, damage, start, end):
    before = damage[damage["reported"] < start]
    during = damage[damage["reported"].between(start, end)]
    t = eq.drop(columns="geometry").copy()
    t["past_damage_400m"] = count_within(eq, before, HISTORY_RADIUS).values
    t["label_damaged"] = (count_within(eq, during, LABEL_RADIUS).values > 0).astype(int)
    # keep the position so weather can be added per location in the next step
    ll = eq.to_crs("EPSG:4326")
    t["lat"], t["lon"] = ll.geometry.y.values, ll.geometry.x.values
    return t


# ------------------------------------------------------------------ main
def main():
    CACHE.mkdir(exist_ok=True)
    print("1. Equipment...")
    eq = load_equipment()

    print("2. Network position from the topology file...")
    net = network_features()
    eq = eq.merge(net, on="location", how="inner")   # keep devices that are on power paths
    print("  ", len(eq), "devices on power paths")

    print("3. Poles and lines around each device...")
    eq = eq.merge(surroundings(eq), on="location", how="left")
    for c in ["poles_nearby", "overhead_line_m", "near_backbone"]:
        eq[c] = eq[c].fillna(0)

    print("4. Damage history and labels per storm...")
    damage = load_damage()
    for name, (start, end) in STORMS.items():
        t = storm_table(eq, damage, pd.Timestamp(start), pd.Timestamp(end) + pd.Timedelta(days=1))
        t["storm"] = name
        t.to_csv(CACHE / f"train_{name}.csv", index=False)
        print(f"   {name}: {len(t)} rows, {t['label_damaged'].sum()} damaged "
              f"({t['label_damaged'].mean():.1%})")


if __name__ == "__main__":
    main()