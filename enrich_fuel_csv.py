"""
Enrich OPIS fuel_prices.csv with lat/lon using Nominatim (OpenStreetMap).
Free, no API key. Rate-limited to 1 req/sec. Uses cache so re-runs are instant.

Reads:  routing/data/fuel_prices.csv
Writes: routing/data/fuel_prices_enriched.csv
Cache:  routing/data/city_coords_cache.json
"""

import csv
import json
import os
import time
import requests
from pathlib import Path


INPUT_CSV   = "data/fuel_prices.csv"
OUTPUT_CSV  = "data/fuel_prices_enriched.csv"
CACHE_FILE  = "data/city_coords_cache.json"

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "fuel-route-optimizer/1.0 (educational project)"


def load_cache():
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE) as f:
            return json.load(f)
    return {}


def save_cache(cache):
    with open(CACHE_FILE, "w") as f:
        json.dump(cache, f, indent=2)


def geocode(city, state):
    """Geocode a US city/state via Nominatim. Returns (lat, lon) or None."""
    try:
        r = requests.get(
            NOMINATIM_URL,
            params={
                "city": city,
                "state": state,
                "country": "USA",
                "format": "json",
                "limit": 1,
            },
            headers={"User-Agent": USER_AGENT},
            timeout=15,
        )
        if r.status_code != 200:
            print(f"(HTTP {r.status_code}) ", end="")
            return None
        data = r.json()
        if not data:
            return None
        return (float(data[0]["lat"]), float(data[0]["lon"]))
    except Exception as e:
        print(f"(err: {e}) ", end="")
        return None


def main():
    input_path = Path(INPUT_CSV)
    if not input_path.exists():
        print(f"{INPUT_CSV} not found")
        return

    with open(input_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fieldnames = reader.fieldnames

    def find_col(*candidates):
        for c in fieldnames:
            for cand in candidates:
                if cand.lower() in c.lower():
                    return c
        return None

    city_col  = find_col("city")
    state_col = find_col("state")

    if not city_col or not state_col:
        print(f"Could not find City/State columns in {fieldnames}")
        return
    cache = load_cache()
    print(f"Cache has {len(cache)} entries")

    unique_cities = set()
    for row in rows:
        city = (row.get(city_col) or "").strip()
        state = (row.get(state_col) or "").strip().upper()
        if city and state:
            unique_cities.add(f"{city}|{state}")

    missing = sorted(c for c in unique_cities if c not in cache)
    for i, key in enumerate(missing, 1):
        city, state = key.split("|", 1)
        print(f"[{i}/{len(missing)}] {city}, {state} ... ", end="", flush=True)

        coords = geocode(city, state)
        if coords:
            cache[key] = {"lat": coords[0], "lon": coords[1]}
            print(f"✅ {coords[0]:.4f}, {coords[1]:.4f}")
        else:
            cache[key] = None
        if i % 20 == 0:
            save_cache(cache)
        time.sleep(1.1)

    save_cache(cache)
    print(f"\nCache saved ({len(cache)} entries)")
    print(f"Writing {OUTPUT_CSV}")
    new_fields = list(fieldnames) + ["latitude", "longitude"]

    matched = 0
    unmatched = 0
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=new_fields)
        writer.writeheader()

        for row in rows:
            city = (row.get(city_col) or "").strip()
            state = (row.get(state_col) or "").strip().upper()
            key = f"{city}|{state}"

            coords = cache.get(key)
            if coords:
                row["latitude"] = coords["lat"]
                row["longitude"] = coords["lon"]
                matched += 1
            else:
                row["latitude"] = ""
                row["longitude"] = ""
                unmatched += 1

            writer.writerow(row)

if __name__ == "__main__":
    main()