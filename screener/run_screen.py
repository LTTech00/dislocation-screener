"""Esegue lo screen completo sui dati reali (gratuiti).

  python -m screener.run_screen             # giro completo
  python -m screener.run_screen --fast      # fondamentali solo per chi passa il trigger
  python -m screener.run_screen --quick     # riusa i fondamentali in cache, aggiorna prezzi+stime
  python -m screener.run_screen --mode or   # trigger meno severo (mercati calmi)
  python -m screener.run_screen --max 60    # prova rapida su un sottoinsieme
"""

from __future__ import annotations

import argparse
import shutil
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from . import config, data, metrics, report, scoring, universe


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Dislocation Screener")
    ap.add_argument("--fast", action="store_true",
                    help="fondamentali solo per i titoli che passano il trigger")
    ap.add_argument("--quick", action="store_true",
                    help="riusa i fondamentali in cache anche se vecchi; aggiorna solo prezzi e stime")
    ap.add_argument("--max", type=int, default=None, help="limita l'universo (debug)")
    ap.add_argument("--mode", choices=["and", "or"], default=None,
                    help="trigger: 'and' severo, 'or' permissivo")
    ap.add_argument("--no-news", action="store_true", help="salta le notizie")
    ap.add_argument("--force-prices", action="store_true",
                    help="riscarica i prezzi ignorando la cache di oggi")
    return ap.parse_args()


def passes_trigger(row: pd.Series, mode: str) -> bool:
    trig = config.DISLOCATION_TRIGGER
    sig = row.get("sigma_move_1m")
    dd = row.get("drawdown_52w")
    cond_sigma = sig is not None and not pd.isna(sig) and sig <= -trig["min_sigma_move_1m"]
    cond_dd = dd is not None and not pd.isna(dd) and dd <= -trig["min_drawdown_52w"]
    return (cond_sigma and cond_dd) if mode == "and" else (cond_sigma or cond_dd)


def main() -> None:
    args = parse_args()
    mode = args.mode or config.DISLOCATION_TRIGGER["mode"]
    started = datetime.now()
    print(f"Dislocation Screener — {started:%d/%m/%Y %H:%M} — trigger mode: {mode}")

    # 1 ------------------------------------------------------------ universo
    print("[1/6] Universo")
    uni = universe.build_universe()
    if args.max:
        uni = uni[: args.max]
        print(f"  Limitato a {len(uni)} titoli (--max)")
    tickers = [u["ticker"] for u in uni]
    meta_uni = {u["ticker"]: u for u in uni}

    # 2 -------------------------------------------------------------- prezzi
    print("[2/6] Prezzi")
    prices = data.load_prices(tickers, force=args.force_prices)
    print(f"  Prezzi disponibili per {len(prices)}/{len(tickers)} titoli")

    price_rows = []
    for t, df in prices.items():
        row = {"ticker": t}
        row.update(metrics.price_metrics(df))
        price_rows.append(row)
    pm = pd.DataFrame(price_rows).set_index("ticker")
    pm["triggered"] = pm.apply(lambda r: passes_trigger(r, mode), axis=1)
    n_trig = int(pm["triggered"].sum())
    print(f"  Trigger di dislocazione superato da {n_trig} titoli")

    # 3 -------------------------------------------------------- fondamentali
    print("[3/6] Fondamentali (la prima volta è il passo lento)")
    scope_all = (config.FUNDAMENTALS_SCOPE == "all") and not args.fast
    fund_targets = list(pm.index) if scope_all else list(pm.index[pm["triggered"]])
    ttl = 10_000 if args.quick else None  # --quick: qualsiasi cache va bene
    funds: dict[str, dict] = {}
    for i, t in enumerate(fund_targets, 1):
        funds[t] = data.fetch_fundamentals(t, ttl_days=ttl)
        if i % 25 == 0 or i == len(fund_targets):
            print(f"    {i}/{len(fund_targets)}")

    # 4 ------------------------------------------------------- stime + cambi
    print("[4/6] Stime di consenso (solo per i titoli oltre il trigger)")
    est_targets = list(pm.index[pm["triggered"]])
    estimates: dict[str, dict] = {}
    for i, t in enumerate(est_targets, 1):
        estimates[t] = data.estimate_changes(data.fetch_estimates(t))
        if i % 25 == 0 or i == len(est_targets):
            print(f"    {i}/{len(est_targets)}")

    currencies = {f.get("currency") for f in funds.values() if f.get("currency")}
    fx, fx_fresh = data.load_fx(currencies)
    if "GBp" in fx and "GBP" not in fx:
        fx["GBP"] = fx["GBp"] * 100.0

    # 5 ------------------------------------------------------ tabella master
    print("[5/6] Score")
    rows = []
    fund_ages = []
    for t in pm.index:
        f = funds.get(t, {})
        e = estimates.get(t, {"d30": None, "d90": None, "has_estimates": False})
        u = meta_uni.get(t, {})
        row = {"ticker": t, "region": u.get("region"), "semis": u.get("semis"),
               "name": f.get("name") or t, "sector": f.get("sector"),
               "currency": f.get("currency"),
               "forward_pe": f.get("forward_pe"), "trailing_pe": f.get("trailing_pe"),
               "price_to_book": f.get("price_to_book"), "roe": f.get("roe"),
               "short_pct_float": f.get("short_pct_float"),
               "eps_d30": e.get("d30"), "eps_d90": e.get("d90"),
               "has_estimates": bool(e.get("has_estimates"))}
        row.update(pm.loc[t].to_dict())
        row.update(metrics.fundamental_metrics(f))

        cur = f.get("currency")
        rate = fx.get("GBP" if cur == "GBp" else cur) if cur else None
        cap = f.get("market_cap")
        row["market_cap_usd"] = cap * rate if (cap and rate) else None
        av = row.get("avg_value_traded_local")
        row["avg_dollar_volume"] = av * fx.get(cur, np.nan) if (av and cur) else None

        row["confidence"] = data.confidence_of(
            f, row["has_estimates"], row.get("history_days", 0) >= 60)
        if f.get("_fetched_at"):
            try:
                fund_ages.append(
                    (datetime.now() - datetime.fromisoformat(f["_fetched_at"])).days)
            except Exception:
                pass
        rows.append(row)
    master = pd.DataFrame(rows)

    ex = config.HARD_EXCLUSIONS
    gated = master[
        master["market_cap_usd"].fillna(0).ge(ex["min_market_cap_usd"])
        & master["avg_dollar_volume"].fillna(0).ge(ex["min_avg_dollar_volume"])
        & master["history_days"].fillna(0).ge(ex["min_price_history_days"])
    ].copy()
    print(f"  Dopo le esclusioni dure: {len(gated)} titoli "
          f"(esclusi {len(master) - len(gated)})")

    scored = scoring.score_universe(gated)
    final = scored[
        scored["triggered"]
        & scored["confidence"].fillna(0).ge(ex["min_confidence"])
    ].sort_values("score", ascending=False).reset_index(drop=True)
    print(f"  In classifica: {len(final)} titoli oltre il trigger")

    # 6 ------------------------------------------------------------- output
    print("[6/6] Notizie e output")
    if not args.no_news and len(final):
        top_n = final.head(config.DATA["news_top_n"])
        news_map = {}
        for i, t in enumerate(top_n["ticker"], 1):
            news_map[t] = data.fetch_news(t)
            if i % 25 == 0 or i == len(top_n):
                print(f"    notizie {i}/{len(top_n)}")
        final["news"] = final["ticker"].map(lambda t: news_map.get(t, []))
    else:
        final["news"] = [[] for _ in range(len(final))]

    out_dir = Path("output")
    out_dir.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d")
    est_cov = (100.0 * final["has_estimates"].mean()) if len(final) else None
    meta = {
        "generatedAt": datetime.now().isoformat(timespec="seconds"),
        "pricesDate": (str(pm["last_price_date"].dropna().max())
                       if "last_price_date" in pm else None),
        "universeCount": len(uni),
        "gatedCount": len(gated),
        "triggeredCount": len(final),
        "fundAgeMedianDays": float(np.median(fund_ages)) if fund_ages else None,
        "estCoveragePct": est_cov,
        "fxFresh": fx_fresh,
        "synthetic": False,
        "weightsDefault": config.WEIGHTS,
        "collapseThreshold": config.THRESHOLDS["estimates_collapse_90d"],
    }

    html_path = out_dir / f"screen_{stamp}.html"
    report.write_report(final, meta, str(html_path), prices)
    shutil.copyfile(html_path, out_dir / "latest.html")

    keep = [c for c in final.columns if c not in ("penalty_items", "news")]
    final.head(100)[keep].to_csv(out_dir / f"screen_{stamp}.csv", index=False)
    scored[keep].to_csv(out_dir / f"raw_{stamp}.csv", index=False)

    elapsed = (datetime.now() - started).seconds
    print(f"\nFatto in {elapsed // 60}m{elapsed % 60:02d}s.")
    print(f"  Dashboard : {html_path}  (copia sempre aggiornata: output/latest.html)")
    print(f"  CSV top   : output/screen_{stamp}.csv")
    print(f"  CSV grezzo: output/raw_{stamp}.csv")
    if len(final):
        print("\nPrimi 10:")
        for _, r in final.head(10).iterrows():
            print(f"  {r['score']:5.1f}  {r['ticker']:<10} {str(r['name'])[:34]:<34} "
                  f"1M {r['ret_1m'] * 100:+5.1f}%  σ {r.get('sigma_move_1m') or 0:+.1f}")
    else:
        print("\nNessun titolo oltre il trigger: mercato calmo. "
              "Prova --mode or, oppure abbassa min_sigma_move_1m in config.py.")


if __name__ == "__main__":
    main()
