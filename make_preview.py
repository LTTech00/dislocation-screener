"""Anteprima della dashboard con DATI SINTETICI (banner rosso ben visibile).

Serve a vedere e provare l'interfaccia in 2 secondi, senza aspettare il
download reale. Passa dallo stesso motore di scoring e dallo stesso generatore
HTML del giro vero: solo i numeri sono inventati.

  python make_preview.py
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from screener import config, report, scoring

COMPANIES = [
    # ticker, nome, regione, settore, semis, financial
    ("IBM", "International Business Machines", "USA", "Technology", False),
    ("NKE", "Nike Inc.", "USA", "Consumer Cyclical", False),
    ("PYPL", "PayPal Holdings", "USA", "Financial Services", False),
    ("CVS", "CVS Health", "USA", "Healthcare", False),
    ("INTC", "Intel Corporation", "USA", "Technology", True),
    ("MU", "Micron Technology", "USA", "Technology", True),
    ("ON", "ON Semiconductor", "USA", "Technology", True),
    ("DE", "Deere & Company", "USA", "Industrials", False),
    ("ABNB", "Airbnb Inc.", "USA", "Consumer Cyclical", False),
    ("RACE.MI", "Ferrari N.V.", "Europa", "Consumer Cyclical", False),
    ("EL.PA", "EssilorLuxottica", "Europa", "Healthcare", False),
    ("KER.PA", "Kering SA", "Europa", "Consumer Cyclical", False),
    ("ASML", "ASML Holding", "Europa", "Technology", True),
    ("STM", "STMicroelectronics", "Europa", "Technology", True),
    ("ADYEN.AS", "Adyen N.V.", "Europa", "Technology", False),
    ("BAYN.DE", "Bayer AG", "Europa", "Healthcare", False),
    ("HSBA.L", "HSBC Holdings", "Europa", "Financial Services", False),
    ("005930.KS", "Samsung Electronics", "Asia", "Technology", True),
    ("TSM", "Taiwan Semiconductor (TSMC)", "Asia", "Technology", True),
    ("000660.KS", "SK Hynix", "Asia", "Technology", True),
    ("8035.T", "Tokyo Electron", "Asia", "Technology", True),
    ("6758.T", "Sony Group", "Asia", "Technology", False),
    ("BABA", "Alibaba Group (ADR)", "Asia", "Consumer Cyclical", False),
    ("7974.T", "Nintendo Co.", "Asia", "Communication Services", False),
    ("1299.HK", "AIA Group", "Asia", "Financial Services", False),
    ("7203.T", "Toyota Motor", "Asia", "Consumer Cyclical", False),
]

FAKE_NEWS = [
    {"title": "ESEMPIO — Utili trimestrali sotto le attese, il titolo scivola",
     "link": "https://example.com", "publisher": "Notizia sintetica",
     "date": datetime.now().strftime("%Y-%m-%d")},
    {"title": "ESEMPIO — Il settore arretra dopo i nuovi dazi annunciati",
     "link": "https://example.com", "publisher": "Notizia sintetica", "date": ""},
]


def build_synthetic(seed: int = 7) -> pd.DataFrame:
    rng = np.random.RandomState(seed)
    rows = []
    for ticker, name, region, sector, semi in COMPANIES:
        ret_1m = float(rng.uniform(-0.30, -0.07))
        vol = float(rng.uniform(0.16, 0.55))
        eps_d30 = float(np.clip(rng.normal(-0.03, 0.07), -0.35, 0.05))
        eps_d90 = float(np.clip(eps_d30 * rng.uniform(1.0, 2.6), -0.45, 0.05))
        has_est = bool(rng.rand() > 0.12)
        fin = sector == "Financial Services"
        rows.append({
            "ticker": ticker, "name": name, "region": region, "sector": sector,
            "semis": semi, "currency": "USD", "triggered": True,
            "history_days": 380,
            "last_close": round(float(rng.uniform(20, 900)), 2),
            "last_price_date": datetime.now().strftime("%Y-%m-%d"),
            "ret_1m": ret_1m, "ret_3m": ret_1m * float(rng.uniform(0.8, 1.6)),
            "vol_annual": vol,
            "sigma_move_1m": ret_1m / (vol / np.sqrt(12)),
            "drawdown_52w": ret_1m * float(rng.uniform(1.0, 1.8)),
            "crash_concentration": float(rng.uniform(0.2, 1.2)),
            "rsi_14": float(rng.uniform(22, 55)),
            "days_since_low_1m": int(rng.randint(0, 15)),
            "capitulation_ratio": float(rng.uniform(1.0, 5.0)),
            "capitulation_decayed": bool(rng.rand() > 0.5),
            "roic": None if fin else float(rng.uniform(0.04, 0.30)),
            "roic_trend": None if fin else float(rng.normal(0.0, 0.03)),
            "fcf_conversion": None if fin else float(rng.uniform(0.5, 1.4)),
            "interest_coverage": None if fin else float(rng.uniform(1.5, 25)),
            "margin_stability": None if fin else float(rng.uniform(0.005, 0.05)),
            "revenue_cagr_3y": float(rng.normal(0.05, 0.06)),
            "ev_ebitda": None if fin else float(rng.uniform(6, 28)),
            "net_debt_ebitda": None if fin else float(rng.uniform(-0.5, 4.2)),
            "fcf_yield": None if fin else float(rng.uniform(0.01, 0.09)),
            "fcf": None if fin else float(rng.uniform(-2e9, 2e10)),
            "forward_pe": float(rng.uniform(9, 45)),
            "trailing_pe": float(rng.uniform(9, 50)),
            "price_to_book": float(rng.uniform(0.5, 8)),
            "roe": float(rng.uniform(0.03, 0.30)),
            "short_pct_float": float(rng.uniform(0.005, 0.12)),
            "eps_d30": eps_d30 if has_est else None,
            "eps_d90": eps_d90 if has_est else None,
            "has_estimates": has_est,
            "confidence": round(float(rng.uniform(0.55, 1.0)), 2),
            "market_cap_usd": float(rng.uniform(8e9, 9e11)),
            "avg_dollar_volume": float(rng.uniform(2e7, 3e9)),
        })
    return pd.DataFrame(rows)


def main() -> Path:
    df = build_synthetic()
    scored = scoring.score_universe(df)
    final = scored.sort_values("score", ascending=False).reset_index(drop=True)
    final["news"] = [list(FAKE_NEWS) if i < 8 else [] for i in range(len(final))]

    meta = {
        "generatedAt": datetime.now().isoformat(timespec="seconds"),
        "pricesDate": datetime.now().strftime("%Y-%m-%d"),
        "universeCount": 1042, "gatedCount": 611, "triggeredCount": len(final),
        "fundAgeMedianDays": 2, "estCoveragePct": 88.0, "fxFresh": True,
        "synthetic": True,
        "weightsDefault": config.WEIGHTS,
        "collapseThreshold": config.THRESHOLDS["estimates_collapse_90d"],
    }
    out = Path("output")
    out.mkdir(exist_ok=True)
    path = out / "preview.html"
    report.write_report(final, meta, str(path))
    print(f"Anteprima sintetica scritta in {path} — aprila con un doppio click.")
    return path


if __name__ == "__main__":
    main()
