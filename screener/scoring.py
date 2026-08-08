"""Score composito: percentili cross-sezionali dentro il settore, mai soglie
assolute sui multipli. I finanziari viaggiano su un binario separato
(P/B e ROE al posto di EV/EBITDA e net debt)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import config

FINANCIAL_SECTORS = {"Financial Services", "Financial", "Financials"}
AXES = ["dislocation", "quality", "value", "repricing", "timing"]


# ------------------------------------------------------------- percentili
def sector_pct(df: pd.DataFrame, col: str, higher_is_better: bool = True,
               min_group: int = 8) -> pd.Series:
    """Rank percentile 0-100 dentro il settore; se il gruppo è piccolo,
    media col percentile sull'intero universo."""
    series = pd.to_numeric(df[col], errors="coerce")
    global_pct = series.rank(pct=True) * 100
    sector_ranked = series.groupby(df["sector"].fillna("_na")).rank(pct=True) * 100
    sizes = df.groupby(df["sector"].fillna("_na"))[col].transform(
        lambda s: s.notna().sum())
    blended = np.where(sizes >= min_group, sector_ranked,
                       (sector_ranked.fillna(global_pct) + global_pct) / 2)
    out = pd.Series(blended, index=df.index)
    if not higher_is_better:
        out = 100 - out
    return out


def _avg_available(parts: list[pd.Series], weights: list[float]) -> pd.Series:
    """Media pesata ignorando i NaN riga per riga; NaN se nulla è disponibile."""
    stacked = pd.concat(parts, axis=1)
    w = np.array(weights, dtype=float)
    values = stacked.to_numpy(dtype=float)
    mask = ~np.isnan(values)
    weighted = np.where(mask, values * w, 0.0).sum(axis=1)
    denom = (mask * w).sum(axis=1)
    with np.errstate(invalid="ignore"):
        result = np.where(denom > 0, weighted / denom, np.nan)
    return pd.Series(result, index=stacked.index)


# ----------------------------------------------------------------- assi
def axis_dislocation(df: pd.DataFrame) -> pd.Series:
    sector_median_ret = df.groupby(df["sector"].fillna("_na"))["ret_1m"] \
        .transform("median")
    df = df.assign(excess_1m=df["ret_1m"] - sector_median_ret)
    parts = [
        sector_pct(df, "sigma_move_1m", higher_is_better=False),   # più negativo = meglio
        sector_pct(df, "excess_1m", higher_is_better=False),
        sector_pct(df, "drawdown_52w", higher_is_better=False),
        sector_pct(df, "crash_concentration", higher_is_better=True),
    ]
    return _avg_available(parts, [1.2, 1.0, 0.8, 0.6])


def axis_quality(df: pd.DataFrame) -> pd.Series:
    fin = df["is_financial"]
    normal = _avg_available([
        sector_pct(df, "roic"),
        sector_pct(df, "roic_trend"),
        sector_pct(df, "fcf_conversion"),
        sector_pct(df, "interest_coverage"),
        sector_pct(df, "margin_stability", higher_is_better=False),
    ], [1.3, 1.0, 1.0, 0.7, 0.7])
    financial = _avg_available([
        sector_pct(df, "roe"),
        sector_pct(df, "revenue_cagr_3y"),
    ], [1.5, 0.8])
    return normal.where(~fin, financial)


def axis_value(df: pd.DataFrame) -> pd.Series:
    fin = df["is_financial"]
    normal = _avg_available([
        sector_pct(df, "ev_ebitda", higher_is_better=False),
        sector_pct(df, "forward_pe", higher_is_better=False),
        sector_pct(df, "fcf_yield"),
    ], [1.0, 1.0, 1.0])
    financial = _avg_available([
        sector_pct(df, "price_to_book", higher_is_better=False),
        sector_pct(df, "trailing_pe", higher_is_better=False),
    ], [1.3, 0.8])
    return normal.where(~fin, financial)


def axis_repricing(df: pd.DataFrame) -> pd.Series:
    """gap = Δprezzo − Δstime. Più negativo il gap, più alto il punteggio.
    Se le stime stanno collassando, l'asse viene compresso."""
    gap30 = df["ret_1m"] - df["eps_d30"]
    gap90 = df["ret_3m"] - df["eps_d90"]
    tmp = df.assign(gap30=gap30, gap90=gap90)
    score = _avg_available([
        sector_pct(tmp, "gap30", higher_is_better=False),
        sector_pct(tmp, "gap90", higher_is_better=False),
    ], [1.2, 0.8])
    collapse = df["eps_d90"] < config.THRESHOLDS["estimates_collapse_90d"]
    score = score.where(~collapse, score * config.THRESHOLDS["repricing_compression"])
    # senza stime: sotto la neutralità, non premiato né azzerato
    score = score.where(df["has_estimates"], 35.0)
    return score


def axis_timing(df: pd.DataFrame) -> pd.Series:
    days = pd.to_numeric(df["days_since_low_1m"], errors="coerce")
    stabil = (days.clip(0, 15) / 15.0) * 100

    rsi = pd.to_numeric(df["rsi_14"], errors="coerce")
    rsi_score = (100 - (rsi - 40).abs() * 4).clip(0, 100)  # tenda centrata su 40

    cap_ratio = pd.to_numeric(df["capitulation_ratio"], errors="coerce")
    capit = pd.Series(np.nan, index=df.index)
    capit[cap_ratio.notna()] = 30.0
    strong = (cap_ratio >= 3) & df["capitulation_decayed"].fillna(False)
    partial = (cap_ratio >= 3) & ~df["capitulation_decayed"].fillna(False)
    capit[strong] = 100.0
    capit[partial] = 55.0
    return _avg_available([stabil, rsi_score, capit], [1.0, 1.0, 0.8])


# --------------------------------------------------------------- penalità
def compute_penalties(row: pd.Series) -> tuple[float, list[dict]]:
    p = config.PENALTIES
    t = config.THRESHOLDS
    items: list[dict] = []

    def add(points: float, label: str) -> None:
        items.append({"points": points, "label": label})

    if not row["is_financial"]:
        limit = config.LEVERAGE_LIMITS.get(row.get("sector"),
                                           config.LEVERAGE_LIMITS["_default"])
        nde = row.get("net_debt_ebitda")
        if nde is not None and not pd.isna(nde) and nde > limit:
            add(p["leverage_over_limit"],
                f"Leva {nde:.1f}x oltre il limite di settore ({limit:.1f}x)")
        cov = row.get("interest_coverage")
        if cov is not None and not pd.isna(cov) and cov < t["interest_coverage_min"]:
            add(p["weak_interest_coverage"],
                f"Copertura interessi debole ({cov:.1f}x)")
        fcf = row.get("fcf")
        if fcf is not None and not pd.isna(fcf) and fcf < 0:
            add(p["negative_fcf"], "Free cash flow negativo")

    rev = row.get("revenue_cagr_3y")
    if rev is not None and not pd.isna(rev) and rev < 0:
        add(p["revenue_declining"], f"Ricavi in calo (CAGR 3A {rev:+.1%})")
    trend = row.get("roic_trend")
    if trend is not None and not pd.isna(trend) and trend < -0.01:
        add(p["roic_declining"], "ROIC in calo su 3 anni")
    short = row.get("short_pct_float")
    if short is not None and not pd.isna(short) and short > t["short_interest_max"]:
        add(p["high_short_interest"], f"Short interest alto ({short:.0%})")
    d90 = row.get("eps_d90")
    if d90 is not None and not pd.isna(d90) and d90 < t["estimates_collapse_90d"]:
        add(p["estimates_collapsing"],
            f"Stime EPS in crollo ({d90:+.0%} in 90gg) — possibile drift, non mispricing")
    if not row.get("has_estimates"):
        add(p["estimates_missing"], "Stime di consenso non disponibili")
    if row.get("confidence", 1.0) < t["low_confidence_below"]:
        add(p["low_confidence"], f"Dati incompleti (confidenza {row['confidence']:.0%})")

    total = min(config.MAX_PENALTY, sum(i["points"] for i in items))
    return total, items


# -------------------------------------------------------------- interfaccia
def score_universe(df: pd.DataFrame) -> pd.DataFrame:
    """Aggiunge subscore per asse, penalità e score finale.
    Quality/Value sono percentili su tutto l'universo filtrato (stabili);
    Dislocation/Repricing/Timing hanno senso soprattutto tra i triggered."""
    df = df.copy()
    df["is_financial"] = df["sector"].isin(FINANCIAL_SECTORS)

    df["sub_quality"] = axis_quality(df)
    df["sub_value"] = axis_value(df)

    triggered = df[df["triggered"]].copy()
    if len(triggered):
        df.loc[triggered.index, "sub_dislocation"] = axis_dislocation(triggered)
        df.loc[triggered.index, "sub_repricing"] = axis_repricing(triggered)
        df.loc[triggered.index, "sub_timing"] = axis_timing(triggered)
    for axis in AXES:
        col = f"sub_{axis}"
        if col not in df:
            df[col] = np.nan
        df[col] = pd.to_numeric(df[col], errors="coerce").clip(0, 100).round(1)

    pen_total, pen_items = [], []
    for _, row in df.iterrows():
        total, items = compute_penalties(row)
        pen_total.append(total)
        pen_items.append(items)
    df["penalty_total"] = pen_total
    df["penalty_items"] = pen_items

    weights = config.WEIGHTS
    wsum = sum(weights.values())
    num = sum(df[f"sub_{a}"].fillna(35.0) * w for a, w in weights.items())
    df["score"] = (num / wsum - df["penalty_total"]).clip(0, 100).round(1)
    return df
