"""
TOPBASCH Systems Lab — Léargas SI
ENTSO-E Data Fetcher
Runs via GitHub Actions every 6 hours
"""

import requests
import json
import re
from datetime import datetime, timedelta, timezone

TOKEN = "4b1ded06-e09d-488f-87be-e8535af2e613"
BASE_URL = "https://web-api.tp.entsoe.eu/api"

REGIONS = {
    "10YIE-1001A00010": "Ireland",
    "10Y1001A1001A83F": "Germany",
    "10YFR-RTE------C": "France",
    "10Y1001A1001A65H": "Denmark",
    "10YNL----------L": "Netherlands",
    "10YES-REE------0": "Spain",
}

# Renewable psr types
RENEWABLE_TYPES = {"B01","B09","B10","B11","B12","B16","B17","B18","B19"}
WIND_TYPES = {"B18", "B19"}  # B18=Wind Offshore, B19=Wind Onshore

def get_date_range():
    now = datetime.now(timezone.utc)
    yesterday = now - timedelta(days=1)
    start = yesterday.strftime("%Y%m%d0000")
    end = now.strftime("%Y%m%d%H%M")
    return start, end

def fetch_generation(eic_code):
    start, end = get_date_range()
    params = {
        "securityToken": TOKEN,
        "documentType": "A75",
        "processType": "A16",
        "in_Domain": eic_code,
        "periodStart": start,
        "periodEnd": end,
    }
    try:
        r = requests.get(BASE_URL, params=params, timeout=30)
        r.raise_for_status()
        return r.text
    except Exception as e:
        print(f"Error fetching {eic_code}: {e}")
        return None

def parse_generation(xml):
    if not xml or "<TimeSeries>" not in xml:
        return None

    ts_blocks = re.findall(r"<TimeSeries>([\s\S]*?)</TimeSeries>", xml)
    grouped = {}

    for ts in ts_blocks:
        psr_match = re.search(r"<psrType>(.*?)</psrType>", ts)
        quantities = re.findall(r"<quantity>(\d+\.?\d*)</quantity>", ts)
        if psr_match and quantities:
            psr = psr_match.group(1)
            # Take last available value (most recent period)
            val = float(quantities[-1])
            grouped[psr] = grouped.get(psr, 0) + val

    total_mw = sum(grouped.values())
    renew_mw = sum(v for k, v in grouped.items() if k in RENEWABLE_TYPES)
    wind_mw = sum(v for k, v in grouped.items() if k in WIND_TYPES)
    renew_pct = round(renew_mw / total_mw * 100) if total_mw > 0 else 0

    return {
        "total_mw": round(total_mw),
        "renewable_mw": round(renew_mw),
        "wind_mw": round(wind_mw),
        "renewable_pct": renew_pct,
        "mix": {k: round(v) for k, v in grouped.items()},
    }

def main():
    result = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "regions": {}
    }

    for eic, name in REGIONS.items():
        print(f"Fetching {name}...")
        xml = fetch_generation(eic)
        data = parse_generation(xml)
        if data:
            result["regions"][eic] = {
                "name": name,
                **data
            }
            print(f"  {name}: {data['renewable_pct']}% renewable, {data['wind_mw']}MW wind")
        else:
            print(f"  {name}: no data")

    with open("data/grid_data.json", "w") as f:
        json.dump(result, f, indent=2)

    print(f"\nSaved data for {len(result['regions'])} regions.")

if __name__ == "__main__":
    main()
