# Luxembourg Financial Sector & Labor Market Intelligence Monitor

**A consulting-style data analytics project** analysing the relationship between
Luxembourg's financial sector growth, cross-border labor market dynamics, and
residential housing affordability (2005–2023).

Built as a portfolio project targeting Big 4 consulting internships (PwC, Deloitte,
EY, KPMG) in Luxembourg.

---

## Key findings

- 📌 **Finding 1** — Cross-border workers grew **+71.2%** from 111,200 (2005) to
  190,400 (2023), with French residents representing **54.9%** of the total. The
  cross-border dependency ratio has held structurally stable at **~40%** of total
  Luxembourg employment across two major economic shocks (GFC 2009, COVID 2020).

- 📌 **Finding 2** — Luxembourg's House Price Index reached **210** in 2023 (2010=100)
  — the highest of 6 EU peer countries — growing at **5.18% annually** against wage
  growth of **3.42%**, compounding a structural affordability gap of **1.76pp per year**.
  The housing cost overburden rate rose from 3.8% (2007) to 11.5% (2023).

- 📌 **Finding 3** — Luxembourg's financial sector employs **11.2%** of the domestic
  workforce (NACE K) — 3× Germany (3.7%) and France (3.1%). MFI total assets grew
  **+365%** from €720bn (2005) to €3,350bn (2023). OLS regression between MFI asset
  growth and HPI growth returned R²=0.06, p=0.364 — both variables reflect
  Luxembourg's long-run economic expansion rather than a direct causal relationship.

---

## EU peer benchmarking (2023)

| Country | HPI (2010=100) | Avg gross wage | Fin. emp. share | Overburden rate |
|---|---|---|---|---|
| 🇱🇺 **Luxembourg** | **210** | **€73,200** | **11.2%** | 11.5% |
| 🇩🇪 Germany | 180 | €51,200 | 3.7% | 13.0% |
| 🇮🇪 Ireland | 162 | €58,600 | 7.4% | 4.7% |
| 🇳🇱 Netherlands | 162 | €56,700 | 4.2% | 9.3% |
| 🇧🇪 Belgium | 148 | €52,400 | 3.8% | 7.8% |
| 🇫🇷 France | 131 | €44,800 | 3.1% | 6.5% |

---

## Project structure

```
.
├── data/
│   ├── raw/              # Unmodified source files (never edit these)
│   └── clean/            # Processed CSVs + SQLite database
├── notebooks/
│   ├── 03_eda.ipynb      # Exploratory data analysis + feature engineering
│   └── 04_analysis.ipynb # Regression model + EU benchmarking
├── sql/
│   └── schema.sql        # SQLite schema + 5 analytical views
├── reports/
│   └── charts/           # 13 exported PNG charts
├── powerbi/
│   └── dashboard.pbix    # 3-page interactive Power BI dashboard
├── 01_collect.py         # Data collection from 4 sources (Eurostat, ECB, STATEC)
├── 02_clean.py           # Cleaning pipeline + SQLite loader
├── requirements.txt
└── README.md
```

---

## Data sources

| Source | What it provides | Access |
|---|---|---|
| [Eurostat](https://ec.europa.eu/eurostat) | HPI (prc_hpi_q), housing burden (ilc_lvho07c) | Free SDMX-CSV API |
| [ECB SDW](https://sdw.ecb.europa.eu) | Luxembourg MFI total assets (BSI series) | Free REST API |
| [STATEC](https://lustat.statec.lu) | Cross-border workers by residence country (B1101) | Free CSV download |
| [STATEC / ILO](https://lustat.statec.lu) | Structure of Earnings Survey (wages) | Reference values |

---

## Tech stack

![Python](https://img.shields.io/badge/Python-3.14-blue)
![Pandas](https://img.shields.io/badge/pandas-2.0-blue)
![SQL](https://img.shields.io/badge/SQL-SQLite-lightgrey)
![Power BI](https://img.shields.io/badge/Power%20BI-Dashboard-yellow)
![statsmodels](https://img.shields.io/badge/statsmodels-OLS-green)

---

## Quickstart

```bash
git clone https://github.com/YOUR_USERNAME/luxembourg-analytics.git
cd luxembourg-analytics

pip install -r requirements.txt

python 01_collect.py   # Fetches all raw data → data/raw/
python 02_clean.py     # Cleans + loads SQLite → data/clean/

jupyter lab            # Open notebooks/03_eda.ipynb then 04_analysis.ipynb
```

The Power BI dashboard (`powerbi/dashboard.pbix`) connects to the clean CSVs in
`data/clean/`. Open in Power BI Desktop (free).

---

## Analytical features engineered

**Affordability index:** HPI (2010=100) divided by average gross annual wage,
rebased so 2010=100. Values above 100 indicate housing is less affordable than in
2010 relative to earnings. Luxembourg reached **133** in 2023.

**Cross-border dependency ratio:** Cross-border worker headcount as a percentage
of total Luxembourg employment. Sourced from STATEC indicator B1101. Stable at
**~40%** across 2005–2023.

**MFI 3-year CAGR:** Compound annual growth rate of MFI total assets over rolling
three-year windows. Ranged between **6.2% and 12.0%** across the analysis period.

---

## Regression model

OLS regression with HPI annual growth (%) as the dependent variable and MFI total
assets (€bn) as the primary independent variable.

| Parameter | Value |
|---|---|
| R² | 0.06 |
| p-value | 0.364 |
| Significance | Not significant at 5% level |
| Interpretation | Both variables reflect Luxembourg's long-run economic expansion — not a direct causal relationship |

The level correlation between HPI and MFI assets is r=0.97, but annual growth rates
are uncorrelated. This honest result is reported transparently.

---

## Dashboard structure (Power BI — 3 pages)

**Page 1 — Executive overview:** 4 KPI cards, cross-border worker trend by country,
HPI vs EU peers line chart, year slicer.

**Page 2 — Housing & affordability:** HPI peer comparison, 2023 HPI ranking bar,
Luxembourg overburden rate trend, house price growth vs wage growth.

**Page 3 — Banking & benchmarking:** MFI total assets area chart, peer wage
comparison, financial employment share, key findings text card.

---

## Limitations

- Municipality-level wage data is not publicly available, limiting spatial
  granularity of the affordability index.
- STATEC cross-border data is reported annually with a 12-month publication lag.
- The regression uses observational data; causality cannot be established.
- Financial employment share (NACE K) uses Eurostat LFS reference values as
  granular API data was unavailable at time of analysis.

---

## Summary

> Produced actionable financial sector insights for a Luxembourg Big 4 audience —
> benchmarked across 6 EU countries and 19 years of data — by building an end-to-end
> analytics pipeline using Python, SQL, and Power BI, delivering a 3-page interactive
> dashboard and consulting-style insight report from scratch in 3 days.

---

*University of Luxembourg — Master's in Information and Computer Science (Belval campus)*
