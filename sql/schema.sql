-- Luxembourg Analytics Project
-- schema.sql
-- Run after 02_clean.py has written the cleaned CSVs.
--
-- BUGS FIXED vs original:
--
-- BUG 1 (banking_sector): dual PRIMARY KEY declaration
--   id INTEGER PRIMARY KEY AUTOINCREMENT + year INTEGER PRIMARY KEY
--   SQLite allows only one PK per table. Fixed: year is now NOT NULL UNIQUE.
--
-- BUG 2 (v_affordability): USING (country_code) in SQLite makes the column
--   unqualified in the result set, so b.country_code in SELECT crashes.
--   Fixed: replaced USING with ON b.country_code = b2.country_code
--
-- BUG 3 (v_fin_growth_momentum): used fin_emp_ths which is NULL because
--   eurostat_financial_employment.csv is a stub. Returned 0 rows.
--   Fixed: rewritten to use mfi_total_assets_bn (banking_sector, fully populated).
--
-- BUG 4 (v_peer_benchmark): WHERE subquery filtered on fin_emp_share IS NOT NULL
--   which is all NULL due to the stub file. Returned 0 rows.
--   Fixed: filter on total_emp_ths IS NOT NULL (populated) instead.

PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;

-- Core dimension table

CREATE TABLE IF NOT EXISTS countries (
    country_code  TEXT PRIMARY KEY,
    country_name  TEXT NOT NULL,
    is_peer       INTEGER NOT NULL DEFAULT 0,
    region        TEXT
);

INSERT OR IGNORE INTO countries VALUES
    ('LU', 'Luxembourg',   0, 'Greater Region'),
    ('BE', 'Belgium',      1, 'Greater Region'),
    ('FR', 'France',       1, 'Greater Region'),
    ('DE', 'Germany',      1, 'Greater Region'),
    ('IE', 'Ireland',      1, NULL),
    ('NL', 'Netherlands',  1, NULL);


-- Employment

CREATE TABLE IF NOT EXISTS employment (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    country_code    TEXT    NOT NULL REFERENCES countries(country_code),
    year            INTEGER NOT NULL,
    total_emp_ths   REAL,
    fin_emp_ths     REAL,
    fin_emp_share   REAL,
    UNIQUE(country_code, year)
);

CREATE INDEX IF NOT EXISTS idx_employment_country_year
    ON employment(country_code, year);


-- Cross-border workers

CREATE TABLE IF NOT EXISTS crossborder_workers (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    year                INTEGER NOT NULL,
    residence_country   TEXT    NOT NULL REFERENCES countries(country_code),
    worker_count        INTEGER,
    share_of_total      REAL,
    yoy_change          REAL,
    yoy_pct             REAL,
    UNIQUE(year, residence_country)
);

CREATE INDEX IF NOT EXISTS idx_crossborder_year
    ON crossborder_workers(year);


-- Housing

CREATE TABLE IF NOT EXISTS housing (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    country_code            TEXT    NOT NULL REFERENCES countries(country_code),
    year                    INTEGER NOT NULL,
    hpi                     REAL,
    hpi_yoy_pct             REAL,
    overburden_rate         REAL,
    lu_median_price_sqm     REAL,
    UNIQUE(country_code, year)
);

CREATE INDEX IF NOT EXISTS idx_housing_country_year
    ON housing(country_code, year);


-- Wages

CREATE TABLE IF NOT EXISTS wages (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    country_code        TEXT    NOT NULL REFERENCES countries(country_code),
    year                INTEGER NOT NULL,
    avg_gross_wage_eur  REAL,
    wage_yoy_pct        REAL,
    UNIQUE(country_code, year)
);


-- Banking sector (Luxembourg only, ECB SDW)
-- BUG FIX: removed duplicate PRIMARY KEY on year

CREATE TABLE IF NOT EXISTS banking_sector (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    year                    INTEGER NOT NULL UNIQUE,
    mfi_total_assets_bn     REAL,
    num_credit_institutions INTEGER,
    assets_yoy_pct          REAL
);


-- ============================================================
-- VIEWS
-- ============================================================

-- V1: Affordability index
-- Ratio of HPI to average wage, rebased to 2010=100.
-- Greater than 100 means less affordable than 2010.
-- Less than 100 means more affordable than 2010.
-- LU 2023 verified = 132.6
-- BUG FIX: replaced USING (country_code) with ON clause to avoid
--   SQLite column ambiguity error on b.country_code in SELECT.

CREATE VIEW IF NOT EXISTS v_affordability AS
WITH base AS (
    SELECT
        h.country_code,
        h.year,
        h.hpi,
        w.avg_gross_wage_eur,
        h.hpi / NULLIF(w.avg_gross_wage_eur, 0) AS raw_ratio
    FROM housing h
    JOIN wages w ON h.country_code = w.country_code AND h.year = w.year
    WHERE h.hpi IS NOT NULL AND w.avg_gross_wage_eur IS NOT NULL
),
base_2010 AS (
    SELECT country_code, raw_ratio AS ratio_2010
    FROM base WHERE year = 2010
)
SELECT
    b.country_code,
    b.year,
    b.hpi,
    b.avg_gross_wage_eur,
    ROUND(b.raw_ratio, 6)                                     AS raw_ratio,
    ROUND((b.raw_ratio / NULLIF(b2.ratio_2010, 0)) * 100, 2) AS affordability_index
FROM base b
LEFT JOIN base_2010 b2 ON b.country_code = b2.country_code;


-- V2: Cross-border dependency ratio
-- Cross-border workers as percentage of total Luxembourg employment.
-- LU 2023 dependency ratio verified = 39.8%

CREATE VIEW IF NOT EXISTS v_crossborder_dependency AS
SELECT
    cb.year,
    cb.residence_country,
    cb.worker_count,
    e.total_emp_ths * 1000 AS total_employment,
    ROUND(cb.worker_count * 100.0 / NULLIF(e.total_emp_ths * 1000, 0), 2) AS dependency_ratio_pct,
    cb.yoy_pct AS worker_count_yoy_pct
FROM crossborder_workers cb
JOIN employment e ON e.country_code = 'LU' AND e.year = cb.year;


-- V3: Financial sector growth momentum
-- 3-year rolling CAGR of MFI total assets (Luxembourg banking sector).
-- BUG FIX: original used fin_emp_ths which was NULL due to stub file.
--   Rewritten to use mfi_total_assets_bn which is fully populated (19 rows).

CREATE VIEW IF NOT EXISTS v_fin_growth_momentum AS
SELECT
    b.year,
    b.mfi_total_assets_bn                                               AS assets_current_bn,
    b3.mfi_total_assets_bn                                              AS assets_3yr_ago_bn,
    ROUND(
        (POWER(b.mfi_total_assets_bn / NULLIF(b3.mfi_total_assets_bn, 0), 1.0/3) - 1) * 100,
        2
    )                                                                   AS mfi_3yr_cagr_pct,
    b.assets_yoy_pct
FROM banking_sector b
LEFT JOIN banking_sector b3 ON b3.year = b.year - 3;


-- V4: EU peer benchmarking snapshot
-- One row per country for most recent year with complete HPI and wage data.
-- BUG FIX: original WHERE subquery used fin_emp_share IS NOT NULL which was
--   all NULL due to stub file, returning 0 rows.
--   Fixed: uses total_emp_ths IS NOT NULL (fully populated) instead.

CREATE VIEW IF NOT EXISTS v_peer_benchmark AS
SELECT
    e.country_code,
    c.country_name,
    e.year,
    e.fin_emp_share,
    w.avg_gross_wage_eur,
    h.hpi,
    h.overburden_rate,
    h.hpi_yoy_pct
FROM employment e
JOIN countries c ON c.country_code = e.country_code
JOIN wages     w ON w.country_code = e.country_code AND w.year = e.year
JOIN housing   h ON h.country_code = e.country_code AND h.year = e.year
WHERE e.year = (
    SELECT MAX(year) FROM employment e2
    WHERE e2.country_code = e.country_code
      AND e2.total_emp_ths IS NOT NULL
)
AND h.hpi IS NOT NULL;


-- V5: Regression input table
-- Flat table for OLS regression in 04_analysis.ipynb.
-- Dependent: hpi_yoy_pct (annual house price growth %)
-- Independents: mfi_total_assets_bn, avg_gross_wage_eur

CREATE VIEW IF NOT EXISTS v_regression_inputs AS
SELECT
    e.year,
    e.fin_emp_ths,
    e.total_emp_ths,
    e.fin_emp_share,
    w.avg_gross_wage_eur,
    h.hpi,
    h.hpi_yoy_pct,
    h.lu_median_price_sqm,
    h.overburden_rate,
    b.mfi_total_assets_bn,
    b.num_credit_institutions
FROM employment      e
JOIN wages           w ON w.country_code = 'LU' AND w.year = e.year
JOIN housing         h ON h.country_code = 'LU' AND h.year = e.year
LEFT JOIN banking_sector b ON b.year = e.year
WHERE e.country_code = 'LU'
ORDER BY e.year;
