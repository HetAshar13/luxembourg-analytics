"""
01_collect.py
Luxembourg Financial Sector & Labor Market Intelligence Monitor
Day 1: Data Collection

Sources:
  1. Eurostat  — Labour Force Survey, housing cost burden, house price index
  2. ECB SDW   — Luxembourg banking sector (MFI data)
  3. STATEC    — Cross-border workers, employment by sector
  4. Observatoire de l'Habitat — Residential price index (manual CSV fallback)

Run:
    pip install -r requirements.txt
    python 01_collect.py

All raw files are written to data/raw/.
Nothing is modified here — cleaning happens in 02_clean.py.
"""

import os
import time
import json
import logging
import requests
import pandas as pd

# ── Eurostat helper (no extra dependency needed) ─────────────────────────────
# We use the JSON API directly so the script has zero non-standard dependencies
# beyond requests + pandas.  The eurostat Python package is a thin wrapper
# around the same endpoint; using requests keeps the script self-contained.

EUROSTAT_BASE = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data"
ECB_BASE      = "https://data-api.ecb.europa.eu/service/data"
RAW_DIR       = "data/raw"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Utility helpers
# ─────────────────────────────────────────────────────────────────────────────

def ensure_dirs():
    """Create all project folders if they don't exist yet."""
    for folder in [
        "data/raw", "data/clean",
        "notebooks", "sql", "reports", "powerbi",
    ]:
        os.makedirs(folder, exist_ok=True)
    log.info("Project folders ready.")


def save_raw(df: pd.DataFrame, filename: str):
    path = os.path.join(RAW_DIR, filename)
    df.to_csv(path, index=False)
    log.info(f"  Saved {len(df):,} rows → {path}")


def eurostat_to_df(table_code: str, params: dict) -> pd.DataFrame:
    """
    Fetch a Eurostat JSON-stat table and return a tidy long-format DataFrame.

    The Eurostat JSON-stat format nests dimension labels and a flat 'value'
    array.  We reconstruct the full cartesian index, then zip with values.
    """
    url = f"{EUROSTAT_BASE}/{table_code}"
    log.info(f"  GET Eurostat/{table_code} ...")

    resp = requests.get(url, params={**params, "format": "JSON", "lang": "EN"}, timeout=60)
    resp.raise_for_status()
    data = resp.json()

    dims   = data["id"]                         # ordered list of dimension names
    sizes  = data["size"]                       # number of categories per dimension
    labels = {
        dim: list(data["dimension"][dim]["category"]["label"].values())
        for dim in dims
    }

    # Build a MultiIndex from the cartesian product of all dimension labels
    import itertools
    index_tuples = list(itertools.product(*[labels[d] for d in dims]))
    values       = list(data["value"].values()) if isinstance(data["value"], dict) \
                   else data["value"]

    # Pad values list to match index length (missing cells = None in JSON-stat)
    full_values = [None] * len(index_tuples)
    if isinstance(data["value"], dict):
        for pos_str, val in data["value"].items():
            full_values[int(pos_str)] = val
    else:
        full_values = data["value"]

    df = pd.DataFrame(index_tuples, columns=dims)
    df["value"] = full_values
    return df


# ─────────────────────────────────────────────────────────────────────────────
# 1. Eurostat — Employment by sex, age, country (Labour Force Survey)
#    Table: lfsa_egan   Frequency: annual   Unit: thousands
#    We filter to Luxembourg + peer countries and the 20-64 age group.
# ─────────────────────────────────────────────────────────────────────────────

def fetch_eurostat_employment():
    log.info("Fetching Eurostat employment data (lfsa_egan)...")
    params = {
        "geo":      "LU,BE,FR,DE,IE,NL",
        "age":      "Y20-64",
        "sex":      "T",            # Total
        "unit":     "THS_PER",      # Thousands of persons
        "sinceTimePeriod": "2005",
    }
    try:
        df = eurostat_to_df("lfsa_egan", params)
        df.columns = [c.lower() for c in df.columns]
        df = df.rename(columns={"time_period": "year", "geo\\time": "geo"})
        save_raw(df, "eurostat_employment.csv")
        return df
    except Exception as e:
        log.warning(f"  Eurostat employment fetch failed: {e}. Using fallback stub.")
        return _employment_stub()


def _employment_stub() -> pd.DataFrame:
    """
    Minimal stub so the rest of the pipeline can run even if the API is down.
    Replace with the real fetch once connectivity is confirmed.
    """
    rows = []
    countries = ["LU", "BE", "FR", "DE", "IE", "NL"]
    for country in countries:
        for year in range(2005, 2024):
            rows.append({"geo": country, "year": str(year),
                         "sex": "T", "age": "Y20-64",
                         "unit": "THS_PER", "value": None})
    df = pd.DataFrame(rows)
    save_raw(df, "eurostat_employment.csv")
    return df


# ─────────────────────────────────────────────────────────────────────────────
# 2. Eurostat — Housing cost overburden rate
#    Table: ilc_lvho07c   Unit: % of population
#    Overburden = housing costs > 40% of disposable income
# ─────────────────────────────────────────────────────────────────────────────

def fetch_eurostat_housing_burden():
    log.info("Fetching Eurostat housing cost overburden (ilc_lvho07c)...")
    params = {
        "geo":      "LU,BE,FR,DE,IE,NL,EU27_2020",
        "hhtyp":    "TOTAL",
        "incgrp":   "TOTAL",
        "tenure":   "TOTAL",
        "sinceTimePeriod": "2005",
    }
    try:
        df = eurostat_to_df("ilc_lvho07c", params)
        df.columns = [c.lower() for c in df.columns]
        save_raw(df, "eurostat_housing_burden.csv")
        return df
    except Exception as e:
        log.warning(f"  Housing burden fetch failed: {e}")
        return pd.DataFrame()


# ─────────────────────────────────────────────────────────────────────────────
# 3. Eurostat — House Price Index (HPI)
#    Table: prc_hpi_q   Frequency: quarterly → we'll annualise in 02_clean.py
#    Index base: 2015 = 100
# ─────────────────────────────────────────────────────────────────────────────

def fetch_eurostat_hpi():
    log.info("Fetching Eurostat House Price Index (prc_hpi_q)...")
    params = {
        "geo":      "LU,BE,FR,DE,IE,NL",
        "purchase": "TOTAL",        # All dwellings
        "sinceTimePeriod": "2005Q1",
    }
    try:
        df = eurostat_to_df("prc_hpi_q", params)
        df.columns = [c.lower() for c in df.columns]
        save_raw(df, "eurostat_hpi.csv")
        return df
    except Exception as e:
        log.warning(f"  HPI fetch failed: {e}")
        return pd.DataFrame()


# ─────────────────────────────────────────────────────────────────────────────
# 4. Eurostat — Financial sector employment share
#    Table: nama_10_a64_e   NACE section K = Financial & insurance activities
# ─────────────────────────────────────────────────────────────────────────────

def fetch_eurostat_financial_employment():
    log.info("Fetching Eurostat financial sector employment (nama_10_a64_e)...")
    params = {
        "geo":      "LU,BE,FR,DE,IE,NL",
        "nace_r2":  "K",            # Financial and insurance activities
        "na_item":  "EMP_DC",       # Total employment, domestic concept
        "unit":     "THS_PER",
        "sinceTimePeriod": "2005",
    }
    try:
        df = eurostat_to_df("nama_10_a64_e", params)
        df.columns = [c.lower() for c in df.columns]
        save_raw(df, "eurostat_financial_employment.csv")
        return df
    except Exception as e:
        log.warning(f"  Financial employment fetch failed: {e}")
        return pd.DataFrame()


# ─────────────────────────────────────────────────────────────────────────────
# 5. ECB Statistical Data Warehouse — Luxembourg MFI (banking sector)
#    Series: BSI.A.LU.N.A.A20.A.1.U2.EUR.N
#    = Annual, Luxembourg, MFI total assets, EUR
#    ECB REST API returns SDMX-JSON
# ─────────────────────────────────────────────────────────────────────────────

def fetch_ecb_banking():
    log.info("Fetching ECB banking sector data (MFI total assets)...")

    # Total assets of Luxembourg-resident MFIs (monetary financial institutions)
    series_key = "BSI/BSI.A.LU.N.A.A20.A.1.U2.EUR.N"
    url = f"{ECB_BASE}/{series_key}"

    headers = {"Accept": "application/json"}
    params  = {"startPeriod": "2005", "endPeriod": "2023"}

    try:
        resp = requests.get(url, headers=headers, params=params, timeout=60)
        resp.raise_for_status()
        data = resp.json()

        series = data["dataSets"][0]["series"]
        obs    = list(series.values())[0]["observations"]

        time_dim = data["structure"]["dimensions"]["observation"][0]["values"]

        rows = []
        for i, t in enumerate(time_dim):
            val = obs.get(str(i), [None])[0]
            rows.append({"year": t["id"], "mfi_total_assets_eur_bn": val})

        df = pd.DataFrame(rows)
        df["mfi_total_assets_eur_bn"] = pd.to_numeric(
            df["mfi_total_assets_eur_bn"], errors="coerce"
        ) / 1e9   # Convert to billions

        save_raw(df, "ecb_mfi_assets.csv")
        return df

    except Exception as e:
        log.warning(f"  ECB fetch failed: {e}. Using stub.")
        df = pd.DataFrame({
            "year": [str(y) for y in range(2005, 2024)],
            "mfi_total_assets_eur_bn": [None] * 19,
        })
        save_raw(df, "ecb_mfi_assets.csv")
        return df


# ─────────────────────────────────────────────────────────────────────────────
# 6. ECB — Number of credit institutions in Luxembourg
#    Series: SSI.A.LU.B105.L.EUR._Z.Z.XDC._T.S._X.N
# ─────────────────────────────────────────────────────────────────────────────

def fetch_ecb_num_banks():
    log.info("Fetching ECB number of credit institutions in Luxembourg...")

    series_key = "SSI/SSI.A.LU.B105.L.EUR._Z.Z.XDC._T.S._X.N"
    url = f"{ECB_BASE}/{series_key}"

    headers = {"Accept": "application/json"}
    params  = {"startPeriod": "2005", "endPeriod": "2023"}

    try:
        resp = requests.get(url, headers=headers, params=params, timeout=60)
        resp.raise_for_status()
        data = resp.json()

        series = data["dataSets"][0]["series"]
        obs    = list(series.values())[0]["observations"]
        time_dim = data["structure"]["dimensions"]["observation"][0]["values"]

        rows = [
            {"year": t["id"], "num_credit_institutions": obs.get(str(i), [None])[0]}
            for i, t in enumerate(time_dim)
        ]
        df = pd.DataFrame(rows)
        save_raw(df, "ecb_num_banks.csv")
        return df

    except Exception as e:
        log.warning(f"  ECB num banks fetch failed: {e}")
        return pd.DataFrame()


# ─────────────────────────────────────────────────────────────────────────────
# 7. STATEC — Cross-border workers by country of residence
#    STATEC publishes this in their open data portal as a downloadable CSV.
#    Direct URL to the time series (verified 2024).
# ─────────────────────────────────────────────────────────────────────────────

STATEC_CROSSBORDER_URL = (
    "https://lustat.statec.lu/vis?df[ds]=ds_bistat&df[id]=B1101&df[ag]=STATEC"
    "&df[vs]=1.0&lo=5&lc=en&pd=2000%2C2023&ly[cl]=TIME_PERIOD"
)

# STATEC also exposes a direct CSV download per indicator.
# We use the stable CSV export for cross-border workers (frontaliers).
STATEC_CSV_URL = (
    "https://lustat.statec.lu/api/data/B1101/A..?startPeriod=2000"
    "&endPeriod=2023&format=csvdata&lang=en"
)

def fetch_statec_crossborder():
    log.info("Fetching STATEC cross-border workers data...")
    try:
        resp = requests.get(STATEC_CSV_URL, timeout=60)
        resp.raise_for_status()

        from io import StringIO
        df = pd.read_csv(StringIO(resp.text))
        df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
        save_raw(df, "statec_crossborder.csv")
        return df

    except Exception as e:
        log.warning(f"  STATEC cross-border fetch failed: {e}")
        log.warning("  → Download manually from: https://lustat.statec.lu")
        log.warning("    Indicator B1101 | Export as CSV | Save to data/raw/statec_crossborder.csv")

        # Return a documented stub with the expected schema
        df = pd.DataFrame({
            "time_period": [str(y) for y in range(2000, 2024)],
            "country_of_residence": ["BE"] * 24,
            "obs_value": [None] * 24,
            "obs_status": ["M"] * 24,  # M = missing
        })
        save_raw(df, "statec_crossborder.csv")
        return df


# ─────────────────────────────────────────────────────────────────────────────
# 8. Observatoire de l'Habitat — Luxembourg residential price index
#    Published as Excel files on logement.public.lu.
#    We attempt a direct download; on failure we write a clear manual instruction.
# ─────────────────────────────────────────────────────────────────────────────

HABITAT_URL = (
    "https://logement.public.lu/dam-assets/documents/observatoire/"
    "indices/indices-prix-logement.xlsx"
)

def fetch_habitat_prices():
    log.info("Fetching Observatoire de l'Habitat residential price index...")
    try:
        resp = requests.get(HABITAT_URL, timeout=60)
        resp.raise_for_status()

        path = os.path.join(RAW_DIR, "habitat_prices.xlsx")
        with open(path, "wb") as f:
            f.write(resp.content)
        log.info(f"  Saved Excel → {path}")

        # Parse the first sheet; column layout varies by release year
        df = pd.read_excel(path, sheet_name=0, header=1)
        df.columns = [c.strip().lower().replace(" ", "_").replace(".", "")
                      for c in df.columns.astype(str)]
        csv_path = os.path.join(RAW_DIR, "habitat_prices.csv")
        df.to_csv(csv_path, index=False)
        log.info(f"  Also saved CSV → {csv_path}")
        return df

    except Exception as e:
        log.warning(f"  Habitat price fetch failed: {e}")
        log.warning("  → Download manually from:")
        log.warning("    https://logement.public.lu/en/observatoire/indices.html")
        log.warning("    Save the Excel to data/raw/habitat_prices.xlsx")
        return pd.DataFrame()


# ─────────────────────────────────────────────────────────────────────────────
# 9. Eurostat — Average wages / earnings (Luxembourg + peers)
#    Table: earn_ases_pub   Mean gross annual earnings by NACE activity
# ─────────────────────────────────────────────────────────────────────────────

def fetch_eurostat_wages():
    log.info("Fetching Eurostat wages by sector (earn_ases_pub)...")
    params = {
        "geo":      "LU,BE,FR,DE,IE,NL",
        "nace_r2":  "B-S_X_O",     # Business economy excl. public admin
        "sex":      "T",
        "sizeclas": "TOTAL",
        "sinceTimePeriod": "2006",
    }
    try:
        df = eurostat_to_df("earn_ases_pub", params)
        df.columns = [c.lower() for c in df.columns]
        save_raw(df, "eurostat_wages.csv")
        return df
    except Exception as e:
        log.warning(f"  Wages fetch failed: {e}")
        return pd.DataFrame()


# ─────────────────────────────────────────────────────────────────────────────
# Provenance log — records exactly what was fetched and when
# ─────────────────────────────────────────────────────────────────────────────

def write_provenance(results: dict):
    log_path = os.path.join(RAW_DIR, "_provenance.json")
    record = {
        "fetched_at": pd.Timestamp.now().isoformat(),
        "sources": results,
    }
    with open(log_path, "w") as f:
        json.dump(record, f, indent=2, default=str)
    log.info(f"Provenance log → {log_path}")


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    log.info("=" * 60)
    log.info("Luxembourg Analytics Project — Day 1: Data Collection")
    log.info("=" * 60)

    ensure_dirs()

    results = {}

    fetchers = [
        ("eurostat_employment",         fetch_eurostat_employment),
        ("eurostat_housing_burden",      fetch_eurostat_housing_burden),
        ("eurostat_hpi",                 fetch_eurostat_hpi),
        ("eurostat_financial_employment",fetch_eurostat_financial_employment),
        ("eurostat_wages",               fetch_eurostat_wages),
        ("ecb_mfi_assets",               fetch_ecb_banking),
        ("ecb_num_banks",                fetch_ecb_num_banks),
        ("statec_crossborder",           fetch_statec_crossborder),
        ("habitat_prices",               fetch_habitat_prices),
    ]

    for name, fn in fetchers:
        try:
            df = fn()
            results[name] = {
                "status": "ok" if len(df) > 0 else "stub",
                "rows":   len(df),
            }
        except Exception as e:
            log.error(f"  FAILED {name}: {e}")
            results[name] = {"status": "failed", "error": str(e)}
        time.sleep(0.5)  # Be polite to public APIs

    write_provenance(results)

    # ── Summary ──────────────────────────────────────────────────────────────
    log.info("")
    log.info("─" * 60)
    log.info("COLLECTION SUMMARY")
    log.info("─" * 60)
    ok    = [k for k, v in results.items() if v["status"] == "ok"]
    stubs = [k for k, v in results.items() if v["status"] == "stub"]
    fails = [k for k, v in results.items() if v["status"] == "failed"]

    for k in ok:
        log.info(f"  ✓  {k:<42} {results[k]['rows']:,} rows")
    for k in stubs:
        log.warning(f"  ~  {k:<42} stub (no data yet — check manually)")
    for k in fails:
        log.error(f"  ✗  {k:<42} FAILED")

    log.info("")
    log.info(f"  {len(ok)} fetched  |  {len(stubs)} stubs  |  {len(fails)} failed")
    log.info("Next step → run 02_clean.py")
    log.info("=" * 60)


if __name__ == "__main__":
    main()
