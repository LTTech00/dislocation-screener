"""
Irrobustimento della rete. Serve quasi solo in CI.

Il problema che rompe l'automazione non e' il cron: e' che i runner di GitHub
Actions escono da IP datacenter Azure, e Yahoo Finance li tratta da bot.
Sintomi tipici: HTTP 429, risposte 200 con corpo vuoto, `Ticker.info` che
torna dict vuoti per tutto l'universo. Dal portatile di casa gli stessi
ticker funzionano: e' l'IP, non il codice.

Questo modulo fa tre cose, tutte best-effort e non fatali:
  1. installa una sessione curl_cffi che imita il TLS fingerprint di Chrome
  2. alza i retry interni di yfinance
  3. espone un backoff con jitter per i loop chiamanti

Nessuna di queste rende l'IP residenziale. Riducono i blocchi, non li
eliminano. Se il blocco persiste, la soluzione vera e' un self-hosted
runner (vedi DEPLOY.md).
"""
from __future__ import annotations

import os
import random
import time

_STATE = {"hardened": False, "method": None}


def harden(retries: int = 5) -> str:
    """Configura yfinance per ambienti ostili. Ritorna il metodo riuscito."""
    if _STATE["hardened"]:
        return _STATE["method"] or "none"

    method = "none"

    # --- 1. sessione con impersonation TLS
    try:
        from curl_cffi import requests as cffi
        from yfinance import data as yfdata

        profile = os.environ.get("YF_IMPERSONATE", "chrome")
        session = cffi.Session(impersonate=profile, timeout=30)
        yfdata.YfData(session=session)     # YfData e' un singleton
        method = f"curl_cffi:{profile}"
    except Exception as exc:                                   # noqa: BLE001
        print(f"  [net] impersonation non disponibile ({exc.__class__.__name__})")

    # --- 2. retry interni (l'API e' cambiata tra le versioni di yfinance)
    try:
        import yfinance as yf
        try:
            yf.config.network.retries = retries
        except Exception:                                      # noqa: BLE001
            yf.set_config(retries=retries)
    except Exception:                                          # noqa: BLE001
        pass

    _STATE.update(hardened=True, method=method)
    print(f"  [net] hardening: {method}, retries={retries}")
    return method


def backoff_sleep(attempt: int, base: float = 2.0, cap: float = 90.0) -> None:
    """
    Attesa esponenziale con jitter. Il jitter conta: senza, tutti i retry
    ripartono sincronizzati e ricreano lo stesso picco che ha causato il 429.
    """
    delay = min(cap, base * (2 ** attempt)) * (0.5 + random.random())
    time.sleep(delay)


def is_ci() -> bool:
    return os.environ.get("CI", "").lower() == "true"


def pacing_multiplier() -> float:
    """
    In CI si va piu' piano. Il giro notturno non ha fretta e le pause
    lunghe sono l'unica difesa gratuita contro il rate limiting.
    Sovrascrivibile con SCREENER_PACING.
    """
    override = os.environ.get("SCREENER_PACING")
    if override:
        try:
            return max(1.0, float(override))
        except ValueError:
            pass
    return 3.0 if is_ci() else 1.0
