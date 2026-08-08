"""Configurazione centrale dello screener. Tutto ciò che è regolabile sta qui."""

# ---------------------------------------------------------------- pesi assi
# Regolabili anche dal vivo nella dashboard (i sotto-punteggi sono salvati
# separatamente, il ranking si ricalcola nel browser).
WEIGHTS = {
    "dislocation": 25,
    "quality": 25,
    "value": 20,
    "repricing": 20,
    "timing": 10,
}

# ------------------------------------------------------- trigger dislocazione
DISLOCATION_TRIGGER = {
    # calo dell'ultimo mese in unità di sigma del titolo stesso
    "min_sigma_move_1m": 1.2,
    # drawdown minimo dal massimo a 52 settimane
    "min_drawdown_52w": 0.10,
    # "and": entrambe le condizioni; "or": basta una (mercati calmi)
    "mode": "and",
}

# ----------------------------------------------------------- esclusioni dure
HARD_EXCLUSIONS = {
    "min_market_cap_usd": 5e9,        # capitalizzazione minima in USD
    "min_avg_dollar_volume": 5e6,     # controvalore medio giornaliero (USD)
    "min_price_history_days": 200,    # storia prezzi minima
    "min_confidence": 0.35,           # sotto questa confidenza il titolo esce
}

# ------------------------------------------------- limiti di leva per settore
# net debt / EBITDA oltre il quale scatta la penalità
LEVERAGE_LIMITS = {
    "Utilities": 5.0,
    "Communication Services": 3.5,
    "Real Estate": 6.5,
    "Energy": 2.5,
    "Consumer Defensive": 3.5,
    "Industrials": 3.0,
    "Basic Materials": 2.5,
    "Technology": 2.0,
    "Healthcare": 3.0,
    "Consumer Cyclical": 3.0,
    "_default": 3.0,
    # I finanziari NON usano questo limite: binario separato (P/B, ROE).
}

# --------------------------------------------------------------- penalità
# punti sottratti dallo score finale; il totale è limitato a MAX_PENALTY
PENALTIES = {
    "leverage_over_limit": 7,
    "weak_interest_coverage": 6,   # EBIT / interessi < 3
    "negative_fcf": 8,
    "revenue_declining": 4,        # CAGR ricavi 3Y < 0
    "roic_declining": 4,           # trend ROIC 3Y negativo
    "high_short_interest": 5,      # short interest > 8% del flottante
    "estimates_collapsing": 8,     # stime EPS FY+1 giù oltre il 15% in 90gg
    "estimates_missing": 4,        # nessuna stima disponibile
    "low_confidence": 5,           # confidenza dati < 0.6
}
MAX_PENALTY = 30

# soglie collegate alle penalità
THRESHOLDS = {
    "interest_coverage_min": 3.0,
    "short_interest_max": 0.08,
    "estimates_collapse_90d": -0.15,   # oltre questo calo: asse repricing
    "repricing_compression": 0.40,     # ...compresso a questa frazione
    "low_confidence_below": 0.60,
}

# --------------------------------------------------------------- dati
DATA = {
    "price_period_days": 480,          # ~16 mesi di barre giornaliere
    "fundamentals_ttl_days": 7,        # cache fondamentali
    "estimates_ttl_hours": 20,         # cache stime
    "news_ttl_hours": 20,              # cache notizie
    "fx_ttl_hours": 20,                # cache cambi
    "batch_size": 80,                  # ticker per batch di download prezzi
    "per_ticker_sleep": 0.12,          # pausa tra richieste per singolo ticker
    "news_top_n": 120,                 # notizie solo per i primi N candidati
    "news_max_items": 4,
    "news_max_age_days": 30,
}

# fondamentali per tutto l'universo ("all") o solo per chi passa il trigger
# ("passers", più veloce ma percentili di settore meno stabili)
FUNDAMENTALS_SCOPE = "all"

# ------------------------------------------------- cambi di riserva (statici)
# usati SOLO se il download dei cambi fallisce; la dashboard segnala FX stantii
FALLBACK_FX_TO_USD = {
    "USD": 1.0, "EUR": 1.08, "GBP": 1.27, "GBp": 0.0127, "CHF": 1.12,
    "SEK": 0.095, "DKK": 0.145, "NOK": 0.093, "JPY": 0.0066, "KRW": 0.00072,
    "TWD": 0.031, "HKD": 0.128, "INR": 0.0115, "SGD": 0.74, "AUD": 0.66,
    "CAD": 0.73, "PLN": 0.25,
}
