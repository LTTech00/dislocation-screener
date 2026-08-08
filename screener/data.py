"""Layer dati: yfinance + cache su disco.

Struttura cache (nella cartella del progetto):
  .cache/prices/YYYYMMDD.pkl     prezzi dell'intero universo (1 file al giorno)
  .cache/fund/TICKER.json        fondamentali (TTL 7 giorni)
  .cache/est/TICKER.json         stime EPS (TTL ~1 giorno)
  .cache/news/TICKER.json        notizie (TTL ~1 giorno)
  .cache/fx_YYYYMMDD.json        cambi verso USD

Ogni funzione è difensiva: se un campo manca torna None e il titolo perde
punti di confidenza invece di far saltare la pipeline.
"""

from __future__ import annotations

import json
import math
import pickle
import time
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from . import config

CACHE = Path(".cache")


# ------------------------------------------------------------------ utilità
def _ensure_dirs() -> None:
    for sub in ("prices", "fund", "est", "news"):
        (CACHE / sub).mkdir(parents=True, exist_ok=True)


def _safe_ticker_filename(ticker: str) -> str:
    return ticker.replace("/", "_").replace("^", "_")


def _read_json(path: Path, ttl_hours: float) -> dict | None:
    try:
        if not path.exists():
            return None
        payload = json.loads(path.read_text())
        fetched = datetime.fromisoformat(payload["_fetched_at"])
        if datetime.now() - fetched > timedelta(hours=ttl_hours):
            return None
        return payload
    except Exception:
        return None


def _write_json(path: Path, payload: dict) -> None:
    payload["_fetched_at"] = datetime.now().isoformat()
    path.write_text(json.dumps(payload, default=str))


def _num(value) -> float | None:
    """Converte in float; None per NaN, stringhe vuote, infiniti."""
    try:
        if value is None:
            return None
        out = float(value)
        if math.isnan(out) or math.isinf(out):
            return None
        return out
    except (TypeError, ValueError):
        return None


def _yf():
    try:
        import yfinance as yf
        from . import net
        net.harden()          # no-op dalla seconda chiamata in poi
        return yf
    except ImportError as exc:  # pragma: no cover
        raise SystemExit(
            "yfinance non installato. Esegui: pip install -r requirements.txt"
        ) from exc


def _pace(seconds: float) -> None:
    """Pausa fra richieste, allungata in CI dove il rate limiting morde."""
    from . import net
    time.sleep(seconds * net.pacing_multiplier())


# ------------------------------------------------------------------ prezzi
def load_prices(tickers: list[str], force: bool = False,
                verbose: bool = True) -> dict[str, pd.DataFrame]:
    """Barre giornaliere (Close, Volume) per ticker. Cache: 1 file al giorno."""
    _ensure_dirs()
    today = datetime.now().strftime("%Y%m%d")
    cache_file = CACHE / "prices" / f"{today}.pkl"

    prices: dict[str, pd.DataFrame] = {}
    if cache_file.exists() and not force:
        try:
            prices = pickle.loads(cache_file.read_bytes())
        except Exception:
            prices = {}
    missing = [t for t in tickers if t not in prices]
    if not missing:
        if verbose:
            print(f"  Prezzi: {len(prices)} titoli dalla cache di oggi")
        return {t: prices[t] for t in tickers if t in prices}

    yf = _yf()
    period_days = config.DATA["price_period_days"]
    start = (datetime.now() - timedelta(days=period_days)).strftime("%Y-%m-%d")
    batch = config.DATA["batch_size"]
    if verbose:
        print(f"  Prezzi: scarico {len(missing)} titoli in batch da {batch}...")

    for i in range(0, len(missing), batch):
        chunk = missing[i:i + batch]
        try:
            raw = yf.download(chunk, start=start, auto_adjust=True,
                              group_by="ticker", threads=True, progress=False)
        except Exception as exc:
            print(f"    batch {i // batch + 1}: errore download ({exc})")
            continue
        for t in chunk:
            try:
                try:
                    df = raw[t]
                except Exception:
                    df = raw
                df = df[["Close", "Volume"]].dropna(subset=["Close"])
                if len(df) >= 30:
                    prices[t] = df
            except Exception:
                pass
        if verbose:
            print(f"    batch {i // batch + 1}/{-(-len(missing) // batch)}: "
                  f"totale {len(prices)} titoli con prezzi")
        _pace(0.5)

    # fallback Stooq per i buchi (solo ticker USA senza suffisso)
    still_missing = [t for t in missing if t not in prices and "." not in t]
    for t in still_missing[:40]:
        df = _stooq_prices(t)
        if df is not None:
            prices[t] = df
    try:
        cache_file.write_bytes(pickle.dumps(prices))
    except Exception:
        pass
    return {t: prices[t] for t in tickers if t in prices}


def _stooq_prices(ticker: str) -> pd.DataFrame | None:
    try:
        import requests
        url = f"https://stooq.com/q/d/l/?s={ticker.lower()}.us&i=d"
        resp = requests.get(url, timeout=10)
        if resp.status_code != 200 or "Date" not in resp.text[:100]:
            return None
        from io import StringIO
        df = pd.read_csv(StringIO(resp.text), parse_dates=["Date"])
        df = df.set_index("Date")[["Close", "Volume"]].dropna()
        return df.tail(config.DATA["price_period_days"]) if len(df) >= 30 else None
    except Exception:
        return None


# ------------------------------------------------------------------ cambi
def load_fx(currencies: set[str], verbose: bool = True) -> tuple[dict, bool]:
    """Cambi verso USD. Ritorna (mappa, fx_fresh)."""
    _ensure_dirs()
    today = datetime.now().strftime("%Y%m%d")
    cache_file = CACHE / f"fx_{today}.json"
    cached = _read_json(cache_file, config.DATA["fx_ttl_hours"])
    fx = {k: v for k, v in (cached or {}).items() if not k.startswith("_")}

    needed = {c for c in currencies if c and c not in fx}
    needed.discard("USD")
    fx["USD"] = 1.0
    fresh = True
    if needed:
        yf = _yf()
        for cur in sorted(needed):
            base = "GBP" if cur == "GBp" else cur
            rate = None
            for symbol, invert in ((f"{base}USD=X", False), (f"{base}=X", True)):
                try:
                    hist = yf.Ticker(symbol).history(period="5d")["Close"].dropna()
                    if len(hist):
                        rate = 1.0 / float(hist.iloc[-1]) if invert else float(hist.iloc[-1])
                        break
                except Exception:
                    continue
            if rate is None:
                rate = config.FALLBACK_FX_TO_USD.get(cur)
                fresh = False
                if verbose:
                    print(f"    FX {cur}: uso tasso di riserva statico")
            if cur == "GBp" and rate is not None and rate > 0.1:
                rate = rate / 100.0  # pence -> sterline -> USD
            if rate:
                fx[cur] = rate
        _write_json(cache_file, dict(fx))
    return fx, fresh


# ------------------------------------------------------------- fondamentali
def _pick(frame: pd.DataFrame | None, aliases: list[str]) -> list[float | None]:
    """Estrae una riga da income/balance/cashflow provando più nomi.
    Ritorna la serie annuale dal più recente al più vecchio."""
    if frame is None or getattr(frame, "empty", True):
        return []
    for alias in aliases:
        if alias in frame.index:
            row = frame.loc[alias]
            if isinstance(row, pd.DataFrame):
                row = row.iloc[0]
            return [_num(v) for v in row.tolist()]
    return []


def fetch_fundamentals(ticker: str, ttl_days: float | None = None) -> dict:
    """Fondamentali di un titolo, con cache. Chiavi sempre presenti, valori
    eventualmente None."""
    _ensure_dirs()
    ttl_hours = (ttl_days if ttl_days is not None
                 else config.DATA["fundamentals_ttl_days"]) * 24
    path = CACHE / "fund" / f"{_safe_ticker_filename(ticker)}.json"
    cached = _read_json(path, ttl_hours)
    if cached is not None:
        return cached

    yf = _yf()
    out: dict = {"ticker": ticker}
    try:
        tk = yf.Ticker(ticker)
        try:
            info = tk.get_info()
        except Exception:
            info = getattr(tk, "info", {}) or {}

        out["name"] = info.get("shortName") or info.get("longName") or ticker
        out["sector"] = info.get("sector")
        out["industry"] = info.get("industry")
        out["currency"] = info.get("currency")
        out["market_cap"] = _num(info.get("marketCap"))
        out["shares_out"] = _num(info.get("sharesOutstanding"))
        out["total_debt"] = _num(info.get("totalDebt"))
        out["total_cash"] = _num(info.get("totalCash"))
        out["ebitda"] = _num(info.get("ebitda"))
        out["forward_pe"] = _num(info.get("forwardPE"))
        out["trailing_pe"] = _num(info.get("trailingPE"))
        out["price_to_book"] = _num(info.get("priceToBook"))
        out["roe"] = _num(info.get("returnOnEquity"))
        out["short_pct_float"] = _num(info.get("shortPercentOfFloat"))
        out["free_cashflow_info"] = _num(info.get("freeCashflow"))

        inc = bal = cfs = None
        try:
            inc = tk.income_stmt
        except Exception:
            pass
        try:
            bal = tk.balance_sheet
        except Exception:
            pass
        try:
            cfs = tk.cashflow
        except Exception:
            pass

        out["ebit_hist"] = _pick(inc, ["EBIT", "Operating Income"])
        out["revenue_hist"] = _pick(inc, ["Total Revenue", "Operating Revenue"])
        out["net_income_hist"] = _pick(inc, ["Net Income",
                                             "Net Income Common Stockholders"])
        out["pretax_hist"] = _pick(inc, ["Pretax Income"])
        out["tax_hist"] = _pick(inc, ["Tax Provision"])
        out["interest_expense"] = next(
            iter(_pick(inc, ["Interest Expense",
                             "Interest Expense Non Operating"])), None)
        out["equity_hist"] = _pick(bal, ["Stockholders Equity",
                                         "Common Stock Equity",
                                         "Total Equity Gross Minority Interest"])
        out["debt_hist"] = _pick(bal, ["Total Debt"])
        out["cash_hist"] = _pick(bal, ["Cash And Cash Equivalents",
                                       "Cash Cash Equivalents And Short Term Investments"])
        ocf = _pick(cfs, ["Operating Cash Flow",
                          "Cash Flow From Continuing Operating Activities"])
        capex = _pick(cfs, ["Capital Expenditure"])
        fcf = []
        for i in range(max(len(ocf), len(capex))):
            o = ocf[i] if i < len(ocf) else None
            c = capex[i] if i < len(capex) else None
            fcf.append(o + c if (o is not None and c is not None) else o)
        out["fcf_hist"] = fcf
    except Exception as exc:
        out["_error"] = f"{type(exc).__name__}: {exc}"

    _write_json(path, out)
    _pace(config.DATA["per_ticker_sleep"])
    return out


# ------------------------------------------------------------------ stime
def fetch_estimates(ticker: str) -> dict:
    """Trend delle stime EPS (corrente vs 7/30/60/90 giorni fa) per 0y e +1y."""
    _ensure_dirs()
    path = CACHE / "est" / f"{_safe_ticker_filename(ticker)}.json"
    cached = _read_json(path, config.DATA["estimates_ttl_hours"])
    if cached is not None:
        return cached

    yf = _yf()
    out: dict = {"ticker": ticker}
    try:
        tk = yf.Ticker(ticker)
        trend = None
        for getter in ("eps_trend", "get_eps_trend"):
            try:
                obj = getattr(tk, getter)
                trend = obj() if callable(obj) else obj
                if trend is not None and not getattr(trend, "empty", True):
                    break
            except Exception:
                continue
        if trend is not None and not getattr(trend, "empty", True):
            frame = trend
            if "period" in getattr(frame, "columns", []):
                frame = frame.set_index("period")
            for period in ("0y", "+1y"):
                if period in frame.index:
                    row = frame.loc[period]
                    out[period] = {
                        "current": _num(row.get("current")),
                        "d7": _num(row.get("7daysAgo")),
                        "d30": _num(row.get("30daysAgo")),
                        "d60": _num(row.get("60daysAgo")),
                        "d90": _num(row.get("90daysAgo")),
                    }
    except Exception as exc:
        out["_error"] = f"{type(exc).__name__}: {exc}"

    _write_json(path, out)
    _pace(config.DATA["per_ticker_sleep"])
    return out


def estimate_changes(est: dict) -> dict:
    """Δ% della stima EPS FY+1 (fallback FY0) a 30 e 90 giorni."""
    row = est.get("+1y") or est.get("0y") or {}
    cur = row.get("current")

    def delta(past):
        if cur is None or past is None or abs(past) < 0.02:
            return None
        return max(-1.5, min(1.5, (cur - past) / abs(past)))

    return {"d30": delta(row.get("d30")), "d90": delta(row.get("d90")),
            "has_estimates": cur is not None}


# ------------------------------------------------------------------ notizie
def fetch_news(ticker: str) -> list[dict]:
    """Ultimi titoli di stampa per il ticker (formato yfinance vecchio e nuovo)."""
    _ensure_dirs()
    path = CACHE / "news" / f"{_safe_ticker_filename(ticker)}.json"
    cached = _read_json(path, config.DATA["news_ttl_hours"])
    if cached is not None:
        return cached.get("items", [])

    items: list[dict] = []
    try:
        yf = _yf()
        raw = yf.Ticker(ticker).news or []
        for entry in raw:
            content = entry.get("content", entry)
            title = content.get("title")
            link = (content.get("canonicalUrl") or {}).get("url") \
                if isinstance(content.get("canonicalUrl"), dict) \
                else content.get("link") or entry.get("link")
            provider = content.get("provider")
            publisher = (provider.get("displayName") if isinstance(provider, dict)
                         else content.get("publisher") or entry.get("publisher"))
            ts = content.get("pubDate") or entry.get("providerPublishTime")
            when = None
            try:
                if isinstance(ts, (int, float)):
                    when = datetime.fromtimestamp(ts)
                elif isinstance(ts, str):
                    when = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    when = when.replace(tzinfo=None)
            except Exception:
                when = None
            if not title or not link:
                continue
            if when and (datetime.now() - when).days > config.DATA["news_max_age_days"]:
                continue
            items.append({"title": str(title)[:180], "link": link,
                          "publisher": publisher or "",
                          "date": when.strftime("%Y-%m-%d") if when else ""})
            if len(items) >= config.DATA["news_max_items"]:
                break
    except Exception:
        pass

    _write_json(path, {"items": items})
    _pace(config.DATA["per_ticker_sleep"])
    return items


# --------------------------------------------------------------- confidenza
CONFIDENCE_FIELDS = [
    "sector", "market_cap", "ebitda", "total_debt", "equity_hist",
    "revenue_hist", "fcf_hist", "ebit_hist", "forward_pe",
]


def confidence_of(fund: dict, has_estimates: bool, has_prices: bool) -> float:
    score, total = 0.0, len(CONFIDENCE_FIELDS) + 2
    for field in CONFIDENCE_FIELDS:
        value = fund.get(field)
        ok = bool(value) if isinstance(value, list) else value is not None
        score += 1 if ok else 0
    score += 1 if has_estimates else 0
    score += 1 if has_prices else 0
    return round(score / total, 3)
