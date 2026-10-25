"""
prep.py - load AEP's data, connect it, and save small clean files for the app.

Run once (takes about a minute):
    python prep.py

It creates backend/cache/ with:
    homes.csv        demo homes + risk features + synthetic profiles
    chains.json      each demo home's equipment chain (home -> ... -> main breaker)
    equipment.json   map position of each piece of equipment in those chains
    damage.csv       Feb 2025 storm damage on the demo circuits (with repair hours)
    damage_all.csv   all damage on the demo circuits (for the backtest)
    labor.json       repair hours by damage type (from AEP's labor Excel)
    weather.json     real Feb 2025 storm weather for Roanoke
    meta.json        which circuits we picked and why
"""
from pathlib import Path
import json
import random

import pandas as pd
import geopandas as gpd
import requests

BACKEND = Path(__file__).parent
DATA = BACKEND.parent / "aep_data" / "data" / "extracted"
CACHE = BACKEND / "cache"

STORM_START, STORM_END = "2025-02-13", "2025-02-17"   # the Feb 2025 storm
NUM_DEMO_CIRCUITS = 2        # keeps the web map fast
METERS = "EPSG:32617"        # a map projection in meters (UTM zone 17N, covers Roanoke)


# ---------------------------------------------------------------- customers
def load_customers():
    c = gpd.read_file(DATA / "Data1" / "Customer_Clip.shp")
    c = c[["premise_nu", "kind_of_se", "critical_c", "circuit_id", "city", "geometry"]]
    c = c.rename(columns={
        "premise_nu": "home_id",
        "kind_of_se": "wire_type",      # Overhead / Underground / Unknown
        "critical_c": "life_support",   # "LS Life Support" or "N/A"
    })
    c["life_support"] = c["life_support"] == "LS Life Support"
    c["lat"] = c.geometry.y
    c["lon"] = c.geometry.x
    return c


# ---------------------------------------------------------------- network chains
def load_chains():
    """home_id -> list of equipment, from the home up to the main breaker."""
    chains = {}
    with open(DATA / "matched_upstream" / "matched_upstream.txt") as f:
        for line in f:
            parts = line.strip().split("\t")
            home_id, items = parts[0], parts[1:]
            chain = []
            for item in items:
                layer, eq_id, kind, location = item.split("*")
                chain.append({"id": eq_id, "kind": kind, "location": location})
            chains[home_id] = chain
    return chains


# ---------------------------------------------------------------- equipment positions
def load_equipment():
    """Transformers, fuses, reclosers and switches, with their map position."""
    files = {
        "Transformer": DATA / "Data2" / "Transformer_Clip.shp",
        "Fuse": DATA / "Data1" / "Fuse_Bank_Clip.shp",
        "Recloser": DATA / "Data2" / "Recloser_Bank_Clip.shp",
        "Switch": DATA / "Data2" / "Switch_Clip.shp",
    }
    parts = []
    for kind, path in files.items():
        g = gpd.read_file(path, columns=["location_n"])
        g["kind"] = kind
        parts.append(g)
    eq = pd.concat(parts, ignore_index=True)
    eq = gpd.GeoDataFrame(eq, geometry="geometry", crs=parts[0].crs)
    eq = eq.dropna(subset=["location_n"]).rename(columns={"location_n": "location"})
    return eq


# ---------------------------------------------------------------- damage
def load_damage():
    d = gpd.read_file(DATA / "Data1" / "arcos_prod_damage_09_28_Clip.shp")
    d = d[["Circuit", "Substation", "Asset_Type", "Inform_Wor", "Report_Tim",
           "Repaired", "Repaired_D", "Access_Iss", "geometry"]]
    d = d.rename(columns={
        "Circuit": "circuit_name", "Asset_Type": "asset_type",
        "Inform_Wor": "damage_type", "Report_Tim": "reported",
        "Repaired_D": "repaired_date", "Access_Iss": "access_issue",
    })
    d["reported"] = pd.to_datetime(d["reported"])
    d["repaired_date"] = pd.to_datetime(d["repaired_date"])
    # repair time in days (dates only, no hours in the data)
    d["repair_days"] = (d["repaired_date"] - d["reported"]).dt.days
    d.loc[d["Repaired"] != "Yes", "repair_days"] = None
    d["in_storm"] = d["reported"].between(STORM_START, STORM_END)
    return d


def circuit_name_to_id():
    """Damage uses names like 'CIR60'; customers use ids like '0000060'."""
    p = gpd.read_file(DATA / "Data1" / "Primary_ExportFeatures.shp",
                      columns=["circuit_id", "aep_circui"], ignore_geometry=True)
    p = p.dropna().drop_duplicates()
    return dict(zip(p["aep_circui"], p["circuit_id"]))


# ---------------------------------------------------------------- labor hours
# From Install_Labor_HackOHIO.xlsx, sheet "Labor time material related".
# Each number = install + removal hours. ASSUMPTIONS are marked.
EXCEL = {
    "pole_medium": 2.502952 + 0.927489,
    "crossarm": 0.374115 + 0.212178,
    "guying": 0.367034 + 0.162207,
    "grounding": 0.531957 + 0.152961,
    "dead_end": 0.107608 + 0.064,
    "insulator": 0.049231 + 0.039385,
    "pin": 0.066065 + 0.042323,
    "equipment_lead": 0.65019 + 0.206095,
    "transformer_avg": 1.25 + 0.89,      # average across sizes in the sheet
    "recloser": 0.572624 + 0.525358,
    "switch": 1.757946 + 1.00973,
    "fuse_cutout": 0.256 + 0.128,
    "service": 1.692981 + 0.48,
}
LABOR_BY_ASSET = {
    # a broken pole: new pole + crossarm + guy wire + grounding
    "Pole": EXCEL["pole_medium"] + EXCEL["crossarm"] + EXCEL["guying"] + EXCEL["grounding"],
    # ASSUMPTION: the sheet has no wire-pulling hours, so a wire repair =
    # 2 dead-ends + 3 insulators + 3 pins + 1 equipment lead
    "primary": 2 * EXCEL["dead_end"] + 3 * EXCEL["insulator"] + 3 * EXCEL["pin"] + EXCEL["equipment_lead"],
    "secondary": EXCEL["service"],
    "Transformer": EXCEL["transformer_avg"],
    "Recloser Bank": EXCEL["recloser"],
    "Switch": EXCEL["switch"],
    "Fuse Bank": EXCEL["fuse_cutout"],
    "default": EXCEL["equipment_lead"],   # anything else (lights, capacitors)
}
INDIRECT_MULTIPLIER = 4.5         # drive time, safety talk, setup (from the Excel)
ACCESS_ADDER_HOURS = 0.5          # "Restricted Access Work" (from the Excel)


# ---------------------------------------------------------------- weather
def get_storm_weather():
    """Real Feb 2025 weather in Roanoke from Open-Meteo (free, no key)."""
    url = "https://archive-api.open-meteo.com/v1/archive"
    params = {
        "latitude": 37.27, "longitude": -79.94,
        "start_date": "2025-02-12", "end_date": "2025-02-18",
        "hourly": "wind_gusts_10m,wind_speed_10m,precipitation",
        "wind_speed_unit": "mph", "precipitation_unit": "inch",
        "timezone": "America/New_York",
    }
    try:
        r = requests.get(url, params=params, timeout=30)
        r.raise_for_status()
        h = r.json()["hourly"]
        df = pd.DataFrame(h)
        worst = df.loc[df["wind_gusts_10m"].idxmax()]
        return {
            "storm": "Feb 2025, Roanoke VA",
            "source": "Open-Meteo historical archive",
            "max_gust_mph": round(float(worst["wind_gusts_10m"]), 1),
            "max_gust_time": worst["time"],
            "max_wind_mph": round(float(df["wind_speed_10m"].max()), 1),
            "total_rain_in": round(float(df["precipitation"].sum()), 2),
            "hourly": h,
        }
    except Exception as e:
        print("  ! weather download failed, using a placeholder:", e)
        return {"storm": "Feb 2025, Roanoke VA", "source": "PLACEHOLDER (download failed)",
                "max_gust_mph": 50.0, "max_gust_time": None,
                "max_wind_mph": None, "total_rain_in": None, "hourly": None}


# ---------------------------------------------------------------- synthetic profiles
def add_synthetic_profiles(homes):
    """Made-up household details so prep tips can be personal. Clearly labeled."""
    rng = random.Random(42)   # same result every run
    homes["profile_is_synthetic"] = True
    homes["has_sump_pump"] = [rng.random() < 0.25 for _ in range(len(homes))]
    homes["medical_device"] = [rng.random() < 0.05 for _ in range(len(homes))]
    homes["elderly_resident"] = [rng.random() < 0.20 for _ in range(len(homes))]
    homes["works_from_home"] = [rng.random() < 0.30 for _ in range(len(homes))]
    homes["has_generator"] = [rng.random() < 0.15 for _ in range(len(homes))]
    # real life-support customers always count as needing power for medical reasons
    homes.loc[homes["life_support"], "medical_device"] = True
    return homes


# ---------------------------------------------------------------- main
def main():
    CACHE.mkdir(exist_ok=True)

    print("1. Loading customers...")
    customers = load_customers()
    print("  ", len(customers), "homes")

    print("2. Loading damage and picking demo circuits...")
    damage = load_damage()
    name_to_id = circuit_name_to_id()
    damage["circuit_id"] = damage["circuit_name"].map(name_to_id)
    storm = damage[damage["in_storm"]]

    # storm damage within 400 m of each home (for ALL homes, to pick good demo circuits)
    customers_m = customers.to_crs(METERS)
    zones = storm.to_crs(METERS)[["geometry"]].copy()
    zones["geometry"] = zones.buffer(400)
    near = gpd.sjoin(customers_m[["home_id", "geometry"]], zones, predicate="within")
    customers["nearby_damage_storm"] = customers["home_id"].map(
        near.groupby("home_id").size()).fillna(0).astype(int)

    # demo circuits = the ones with the most homes near storm damage
    homes_near = (customers[customers["nearby_damage_storm"] > 0]
                  .groupby("circuit_id").size().sort_values(ascending=False))
    top = homes_near.head(NUM_DEMO_CIRCUITS)
    demo_circuits = list(top.index)
    print("   demo circuits:", {k: int(v) for k, v in top.items()}, "(homes near storm damage)")

    homes = customers[customers["circuit_id"].isin(demo_circuits)].copy()
    print("  ", len(homes), "demo homes")

    print("3. Loading network chains...")
    all_chains = load_chains()
    chains = {h: all_chains[h] for h in homes["home_id"] if h in all_chains}
    homes["has_chain"] = homes["home_id"].isin(chains.keys())
    homes["chain_length"] = homes["home_id"].map(lambda h: len(chains.get(h, [])))
    print("  ", len(chains), "demo homes have a chain")

    print("4. Placing equipment and matching storm damage to it...")
    eq = load_equipment()
    needed = {step["location"] for ch in chains.values() for step in ch}
    eq = eq[eq["location"].isin(needed)].drop_duplicates("location")
    equipment = {row.location: {"kind": row.kind, "lat": row.geometry.y, "lon": row.geometry.x}
                 for row in eq.itertuples()}

    # damage in the demo area = within 400 m of any demo home
    area = homes.to_crs(METERS).buffer(400).union_all()
    dmg_all_m = damage.to_crs(METERS)
    demo_damage = damage[dmg_all_m.within(area)].copy()
    dmg_m = demo_damage.to_crs(METERS)
    eq_m = eq.to_crs(METERS)
    # each damage point -> nearest chain equipment within 100 m (if any)
    matched = gpd.sjoin_nearest(dmg_m, eq_m[["location", "geometry"]],
                                how="left", max_distance=100, distance_col="dist_m")
    matched = matched[~matched.index.duplicated()]
    demo_damage["equipment_location"] = matched["location"]

    # repair hours per damage record
    base = demo_damage["asset_type"].map(LABOR_BY_ASSET).fillna(LABOR_BY_ASSET["default"])
    adder = demo_damage["access_issue"].eq("Yes") * ACCESS_ADDER_HOURS
    demo_damage["labor_hours"] = (base + adder).round(2)

    print("5. Computing risk features per home...")
    storm_dmg = demo_damage[demo_damage["in_storm"]]
    damaged_locations = set(storm_dmg["equipment_location"].dropna())

    homes["circuit_damage_storm"] = homes["circuit_id"].map(
        storm_dmg["circuit_id"].value_counts()).fillna(0).astype(int)
    homes["circuit_damage_history"] = homes["circuit_id"].map(
        demo_damage[~demo_damage["in_storm"]]["circuit_id"].value_counts()).fillna(0).astype(int)
    homes["damaged_on_chain"] = homes["home_id"].map(
        lambda h: sum(step["location"] in damaged_locations for step in chains.get(h, [])))

    homes = add_synthetic_profiles(homes)

    print("6. Getting real storm weather...")
    weather = get_storm_weather()
    print("   max gust:", weather["max_gust_mph"], "mph at", weather["max_gust_time"])

    print("7. Saving to backend/cache/ ...")
    homes.drop(columns="geometry").to_csv(CACHE / "homes.csv", index=False)
    (CACHE / "chains.json").write_text(json.dumps(chains))
    (CACHE / "equipment.json").write_text(json.dumps(equipment))
    keep = ["circuit_id", "circuit_name", "asset_type", "damage_type", "reported",
            "repaired_date", "repair_days", "access_issue", "equipment_location",
            "labor_hours", "in_storm"]
    out = demo_damage[keep].copy()
    out["lat"], out["lon"] = demo_damage.geometry.y, demo_damage.geometry.x
    out[out["in_storm"]].to_csv(CACHE / "damage.csv", index=False)
    out.to_csv(CACHE / "damage_all.csv", index=False)
    (CACHE / "labor.json").write_text(json.dumps({
        "hours_by_asset": {k: round(v, 2) for k, v in LABOR_BY_ASSET.items()},
        "indirect_multiplier": INDIRECT_MULTIPLIER,
        "access_adder_hours": ACCESS_ADDER_HOURS,
        "note": "Hours = install + removal from AEP's labor Excel. Wire repair is an assumption "
                "(the sheet has no wire-pulling hours). Unit (person- vs crew-hours) to confirm with AEP.",
    }, indent=2))
    (CACHE / "weather.json").write_text(json.dumps(weather))
    (CACHE / "meta.json").write_text(json.dumps({
        "demo_circuits": demo_circuits,
        "homes_near_storm_damage_per_circuit": {k: int(v) for k, v in top.items()},
        "storm_window": [STORM_START, STORM_END],
        "num_homes": len(homes),
    }, indent=2))

    print("\nDone. Example home:")
    ex = homes[homes["damaged_on_chain"] > 0].head(1)
    if ex.empty:
        ex = homes.head(1)
    print(ex.drop(columns="geometry").T.to_string())


if __name__ == "__main__":
    main()