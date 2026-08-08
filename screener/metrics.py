"""Metriche calcolate sulle serie di prezzo e sui fondamentali."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd


def _ret(close: pd.Series, days: int) -> float | None:
    if len(close) <= days:
        return None
    prev = float(close.iloc[-days - 1])
    return float(close.iloc[-1]) / prev - 1.0 if prev > 0 else None


def price_metrics(df: pd.DataFrame) -> dict:
    """df con colonne Close e Volume, indice datetime giornaliero."""
    close = df["Close"].dropna()
    volume = df["Volume"].fillna(0)
    out: dict = {"history_days": len(close)}
    if len(close) < 60:
        return out

    out["last_close"] = float(close.iloc[-1])
    out["last_price_date"] = close.index[-1].strftime("%Y-%m-%d")
    out["ret_1m"] = _ret(close, 21)
    out["ret_3m"] = _ret(close, 63)

    daily = close.pct_change().dropna().tail(252)
    vol_d = float(daily.std())
    out["vol_annual"] = vol_d * math.sqrt(252) if vol_d > 0 else None
    if out["ret_1m"] is not None and vol_d > 0:
        out["sigma_move_1m"] = out["ret_1m"] / (vol_d * math.sqrt(21))
    else:
        out["sigma_move_1m"] = None

    high_52w = float(close.tail(252).max())
    out["drawdown_52w"] = out["last_close"] / high_52w - 1.0 if high_52w > 0 else None

    # concentrazione del calo: quanto del movimento mensile sta nei 3 giorni peggiori
    if len(daily) >= 21 and out["ret_1m"] is not None and out["ret_1m"] < -0.02:
        worst3 = float(daily.tail(21).nsmallest(3).sum())
        out["crash_concentration"] = min(1.5, max(0.0, worst3 / out["ret_1m"]))
    else:
        out["crash_concentration"] = None

    # RSI(14)
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / 14, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / 14, adjust=False).mean()
    last_gain, last_loss = float(gain.iloc[-1]), float(loss.iloc[-1])
    if last_loss > 0:
        out["rsi_14"] = 100.0 - 100.0 / (1.0 + last_gain / last_loss)
    else:
        out["rsi_14"] = 100.0 if last_gain > 0 else 50.0

    # giorni trascorsi dal minimo dell'ultimo mese
    tail = close.tail(21)
    out["days_since_low_1m"] = int(len(tail) - 1 - int(np.argmin(tail.values)))

    # volume di capitolazione: picco recente vs media, poi decadimento
    if len(volume) >= 100:
        base = float(volume.tail(100).head(90).mean())
        recent = volume.tail(10)
        peak = float(recent.max())
        after_peak = recent.iloc[int(np.argmax(recent.values)) + 1:]
        decayed = bool(len(after_peak)) and float(after_peak.mean()) < 0.7 * peak
        out["capitulation_ratio"] = peak / base if base > 0 else None
        out["capitulation_decayed"] = decayed
    else:
        out["capitulation_ratio"] = None
        out["capitulation_decayed"] = False

    # controvalore medio giornaliero in valuta locale (60 giorni)
    tail60 = df.tail(60)
    out["avg_value_traded_local"] = float(
        (tail60["Close"] * tail60["Volume"]).mean())
    return out


# ------------------------------------------------------------- fondamentali
def _tax_rate(pretax: float | None, tax: float | None) -> float:
    if pretax and tax and pretax > 0 and 0 <= tax / pretax < 0.6:
        return tax / pretax
    return 0.23


def roic_series(fund: dict) -> list[float]:
    """ROIC per gli ultimi anni disponibili (dal più recente)."""
    ebit = fund.get("ebit_hist") or []
    equity = fund.get("equity_hist") or []
    debt = fund.get("debt_hist") or []
    cash = fund.get("cash_hist") or []
    pretax = fund.get("pretax_hist") or []
    tax = fund.get("tax_hist") or []
    out = []
    for i in range(min(len(ebit), len(equity), 4)):
        e = ebit[i]
        eq = equity[i]
        if e is None or eq is None:
            continue
        d = debt[i] if i < len(debt) and debt[i] is not None else 0.0
        c = cash[i] if i < len(cash) and cash[i] is not None else 0.0
        invested = eq + d - c
        if invested <= 0:
            continue
        rate = _tax_rate(pretax[i] if i < len(pretax) else None,
                         tax[i] if i < len(tax) else None)
        out.append(e * (1 - rate) / invested)
    return out


def _cagr(series: list[float | None], years: int = 3) -> float | None:
    values = [v for v in (series or []) if v is not None]
    if len(values) < years + 1:
        return None
    last, first = values[0], values[years]
    if first is None or last is None or first <= 0 or last <= 0:
        return None
    return (last / first) ** (1.0 / years) - 1.0


def fundamental_metrics(fund: dict) -> dict:
    out: dict = {}
    roics = roic_series(fund)
    out["roic"] = roics[0] if roics else None
    out["roic_trend"] = (roics[0] - roics[-1]) if len(roics) >= 3 else None

    ni = (fund.get("net_income_hist") or [None])[0]
    fcf_hist = fund.get("fcf_hist") or []
    fcf = fcf_hist[0] if fcf_hist else fund.get("free_cashflow_info")
    out["fcf"] = fcf
    out["fcf_conversion"] = (fcf / ni) if (fcf is not None and ni and ni > 0) else None

    ebit = (fund.get("ebit_hist") or [None])[0]
    interest = fund.get("interest_expense")
    if ebit is not None and interest not in (None, 0):
        out["interest_coverage"] = abs(ebit / interest) if ebit > 0 else 0.0
    else:
        out["interest_coverage"] = None

    revenue = fund.get("revenue_hist") or []
    out["revenue_cagr_3y"] = _cagr(revenue)

    # stabilità del margine operativo (deviazione std su 4 anni)
    ebit_hist = fund.get("ebit_hist") or []
    margins = []
    for i in range(min(len(ebit_hist), len(revenue), 4)):
        if ebit_hist[i] is not None and revenue[i]:
            margins.append(ebit_hist[i] / revenue[i])
    out["op_margin"] = margins[0] if margins else None
    out["margin_stability"] = float(np.std(margins)) if len(margins) >= 3 else None

    cap = fund.get("market_cap")
    debt = fund.get("total_debt") or 0.0
    cash = fund.get("total_cash") or 0.0
    ebitda = fund.get("ebitda")
    if cap and ebitda and ebitda > 0:
        out["ev_ebitda"] = (cap + debt - cash) / ebitda
        out["net_debt_ebitda"] = (debt - cash) / ebitda
    else:
        out["ev_ebitda"] = None
        out["net_debt_ebitda"] = None
    out["fcf_yield"] = (fcf / cap) if (fcf is not None and cap) else None
    return out
