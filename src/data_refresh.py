import requests, json, time, csv, sys
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
CACHE_DIR = DATA_DIR / "raw"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

WB_INDICATORS = {
    "AG.PRD.CREL.MT": "Cereal production (metric tons)",
    "AG.PRD.RICE.MT": "Rice production (metric tons)",
    "AG.CON.FERT.ZS": "Fertilizer consumption (kg/ha)",
    "AG.PRD.FOOD.XD": "Food production index",
    "PA.NUS.FCRF": "Official exchange rate (USD/XAF)",
    "NY.GDP.DEFL.KD.ZG": "GDP deflator (annual %)",
    "AG.LND.ARBL.ZS": "Arable land (% of land area)",
}

FAO_CROP_CODES = {
    "maize": 56, "rice_paddy": 27, "sorghum": 83, "millet": 79,
    "cassava": 125, "yams": 122,
    "soybeans": 236, "groundnuts": 242, "oil_palm_fruit": 254,
    "cotton": 328, "cashew": 331, "coffee_green": 656, "cocoa_beans": 661,
}


def download_wb(code, name, max_retries=3):
    cache_file = CACHE_DIR / f"wb_{code}.csv"
    if cache_file.exists():
        print(f"  [cached] {code}: {name}")
        return True

    for attempt in range(max_retries):
        try:
            all_data = []
            page = 1
            pages = 1
            while page <= pages:
                url = f"https://api.worldbank.org/v2/country/TG/indicator/{code}?format=json&per_page=100&page={page}"
                r = requests.get(url, timeout=30)
                if r.status_code != 200:
                    print(f"  [HTTP {r.status_code}] {code} page {page}")
                    break
                data = r.json()
                if isinstance(data, list) and len(data) > 1:
                    meta, records = data[0], data[1]
                    pages = meta.get("pages", 1)
                    all_data.extend(records)
                page += 1

            if all_data:
                rows = []
                for d in all_data:
                    if d.get("value") is not None:
                        rows.append({
                            "Year": d["date"],
                            "indicator": code,
                            "indicator_name": name,
                            "value": float(d["value"]),
                        })
                if rows:
                    rows.sort(key=lambda r: int(r["Year"]))
                    with open(cache_file, "w", newline="") as f:
                        w = csv.DictWriter(f, fieldnames=["Year", "indicator", "indicator_name", "value"])
                        w.writeheader()
                        w.writerows(rows)
                    print(f"  [OK] {code}: {len(rows)} obs ({rows[0]['Year']}-{rows[-1]['Year']})")
                    return True
            print(f"  [empty] {code}: no data")
            return False
        except Exception as e:
            print(f"  [retry {attempt+1}] {code}: {e}")
            time.sleep(2 ** attempt)
    print(f"  [FAIL] {code} after {max_retries} retries")
    return False


def try_fao_api():
    print("\n=== FAO API ===")
    for crop, code in FAO_CROP_CODES.items():
        cache_file = CACHE_DIR / f"fao_{crop}.csv"
        if cache_file.exists():
            print(f"  [cached] {crop} (FAO code {code})")
            continue
        try:
            url = f"https://fenixservices.fao.org/faostat/api/v1/en/QAQ?area=217&item={code}&element=5510&year=2000:2024"
            r = requests.get(url, timeout=30)
            if r.status_code == 200:
                data = r.json()
                if "data" in data and data["data"]:
                    rows = []
                    for d in data["data"]:
                        if d.get("Value") is not None:
                            rows.append({"Year": d["Year"], "crop": crop, "production_t": float(d["Value"])})
                    if rows:
                        rows.sort(key=lambda r: r["Year"])
                        with open(cache_file, "w", newline="") as f:
                            w = csv.DictWriter(f, fieldnames=["Year", "crop", "production_t"])
                            w.writeheader()
                            w.writerows(rows)
                        print(f"  [OK] {crop}: {len(rows)} obs ({rows[0]['Year']}-{rows[-1]['Year']})")
                        continue
            print(f"  [no data] {crop}: HTTP {r.status_code}")
        except Exception as e:
            print(f"  [error] {crop}: {e}")
        time.sleep(0.5)


def try_giews_prices():
    print("\n=== GIEWS/FPMA Prices ===")
    cache_file = CACHE_DIR / "giews_togo_prices.csv"
    if cache_file.exists():
        print("  [cached] GIEWS prices")
        return
    try:
        url = "https://fpma-api.azurewebsites.net/api/v1/prices?country=Togo&format=json&limit=500"
        r = requests.get(url, timeout=30)
        if r.status_code == 200:
            data = r.json()
            rows = []
            for d in data:
                if d.get("price") is not None:
                    rows.append({
                        "Year": d.get("year", ""),
                        "month": d.get("month", ""),
                        "crop": d.get("commodity", ""),
                        "market": d.get("market", ""),
                        "price_fcfa": d.get("price", ""),
                        "unit": d.get("unit", ""),
                    })
            if rows:
                with open(cache_file, "w", newline="") as f:
                    w = csv.DictWriter(f, fieldnames=["Year", "month", "crop", "market", "price_fcfa", "unit"])
                    w.writeheader()
                    w.writerows(rows)
                print(f"  [OK] GIEWS: {len(rows)} price observations")
            else:
                print("  [no data] GIEWS returned empty")
        else:
            print(f"  [HTTP {r.status_code}] GIEWS API")
    except Exception as e:
        print(f"  [error] GIEWS: {e}")


def try_fewsnet_prices():
    print("\n=== FEWS NET Prices ===")
    cache_file = CACHE_DIR / "fewsnet_togo_prices.csv"
    if cache_file.exists():
        print("  [cached] FEWS NET prices")
        return
    try:
        url = "https://fews.net/data/price-warning?country=TO&format=json"
        r = requests.get(url, timeout=30)
        if r.status_code == 200:
            data = r.json()
            with open(cache_file, "w") as f:
                json.dump(data, f, indent=2)
            print(f"  [OK] FEWS NET: {len(json.dumps(data))} chars")
        else:
            print(f"  [HTTP {r.status_code}] FEWS NET")
    except Exception as e:
        print(f"  [error] FEWS NET: {e}")


def main():
    print("=" * 50)
    print("DATA REFRESH - Togo Agricultural Dashboard")
    print("=" * 50)

    print("\n=== World Bank Indicators ===")
    for code, name in WB_INDICATORS.items():
        download_wb(code, name)

    try_fao_api()
    try_giews_prices()
    try_fewsnet_prices()

    print("\n" + "=" * 50)
    print("Cached files:")
    for f in sorted(CACHE_DIR.glob("*")):
        size = f.stat().st_size
        print(f"  {f.name} ({size:,} bytes)")

    print("\nDone!")


if __name__ == "__main__":
    main()
