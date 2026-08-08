"""Costruzione dell'universo: USA (S&P 500) + Europa + Asia, con flag semiconduttori.

L'elenco S&P 500 viene scaricato da Wikipedia a runtime; se fallisce si usa il
fallback statico (large cap principali). Europa e Asia sono seed curati:
aggiungi o togli ticker liberamente.

Dove esiste un ADR USA liquido con buona copertura di stime, si preferisce
l'ADR al listino locale (mappa PREFER_ADR).
"""

from __future__ import annotations

# ------------------------------------------------------------------ USA
FALLBACK_US = [
    "AAPL","MSFT","NVDA","AMZN","GOOGL","META","TSLA","AVGO","BRK-B","LLY",
    "JPM","V","UNH","XOM","MA","COST","HD","PG","JNJ","ORCL","ABBV","BAC",
    "CRM","MRK","KO","CVX","AMD","PEP","TMO","WMT","ADBE","MCD","CSCO","ACN",
    "LIN","NFLX","ABT","INTU","IBM","TXN","QCOM","GE","CAT","DIS","VZ","AMGN",
    "PFE","NOW","ISRG","NEE","PM","SPGI","UBER","CMCSA","RTX","GS","AXP","HON",
    "UNP","T","BKNG","LOW","COP","MS","ELV","SYK","BLK","VRTX","PLD","LMT",
    "SCHW","MDT","ADI","C","DE","TJX","AMAT","MMC","BSX","CB","REGN","PGR",
    "SBUX","ETN","CI","MU","BA","GILD","MDLZ","ADP","BX","PANW","ANET","KLAC",
    "SNPS","INTC","CDNS","SO","NKE","ICE","EQIX","SHW","DUK","CME","WM","ZTS",
    "CL","TGT","MCK","CSX","ITW","EMR","ORLY","APH","PH","FCX","PSX","MCO",
    "AON","NXPI","MSI","ROP","PYPL","AJG","TT","ECL","CARR","MAR","WELL","NSC",
    "AIG","AFL","SRE","TRV","DXCM","HUM","SPG","COF","MET","KMB","PSA","GM",
    "STZ","ROST","F","HLT","IDXX","PCAR","OKE","VLO","KDP","DHI","CTAS","GEHC",
    "ON","EW","CPRT","AME","FAST","ODFL","EXC","KR","CTVA","VRSK","LULU","EA",
    "GWW","BKR","AZO","DAL","CCI","D","LEN","URI","PWR","GLW","DOW","HES",
    "XEL","WMB","ED","FANG","CHTR","EL","BIIB","MNST","KHC","HSY","YUM","ADM",
    "DD","MPC","SLB","DVN","HAL","TFC","USB","PNC","ABNB","PLTR","CRWD","MRVL",
    "TER","SWKS","QRVO","GFS","MPWR","MCHP","ARM","SMCI","DELL","HPQ","HPE",
]

# ------------------------------------------------------------------ Europa
EUROPE_SEED = [
    # Francia
    "MC.PA","OR.PA","RMS.PA","TTE.PA","SAN.PA","AIR.PA","SU.PA","AI.PA",
    "EL.PA","KER.PA","BNP.PA","CS.PA","DG.PA","SAF.PA","BN.PA","RI.PA",
    "CAP.PA","GLE.PA","ACA.PA","ENGI.PA","VIE.PA","LR.PA","PUB.PA","HO.PA",
    # Italia
    "RACE.MI","ENEL.MI","ENI.MI","ISP.MI","UCG.MI","G.MI","STLAM.MI",
    "PRY.MI","MONC.MI","TIT.MI","SRG.MI","TRN.MI","LDO.MI","MB.MI","BAMI.MI",
    # Germania
    "SAP.DE","SIE.DE","ALV.DE","DTE.DE","MBG.DE","BMW.DE","VOW3.DE","BAS.DE",
    "BAYN.DE","MUV2.DE","IFX.DE","ADS.DE","DHL.DE","RWE.DE","DB1.DE","EOAN.DE",
    "HEI.DE","MRK.DE","SHL.DE","ZAL.DE","DBK.DE","CBK.DE","RHM.DE","MTX.DE",
    # Paesi Bassi / Belgio
    "ADYEN.AS","PHIA.AS","INGA.AS","HEIA.AS","WKL.AS","PRX.AS","BESI.AS",
    "ASM.AS","AKZA.AS","KPN.AS","ABI.BR","KBC.BR",
    # Svizzera
    "NESN.SW","ROG.SW","NOVN.SW","UBSG.SW","ZURN.SW","CFR.SW","ABBN.SW",
    "SIKA.SW","LONN.SW","GIVN.SW","HOLN.SW","SCMN.SW","GEBN.SW","SLHN.SW",
    # Regno Unito
    "AZN.L","SHEL.L","HSBA.L","ULVR.L","BP.L","GSK.L","RIO.L","DGE.L","REL.L",
    "LSEG.L","BARC.L","LLOY.L","PRU.L","NG.L","RR.L","BA.L","EXPN.L","CPG.L",
    "III.L","GLEN.L","AAL.L","VOD.L","TSCO.L","IMB.L","BATS.L","SGE.L",
    # Nord Europa
    "MAERSK-B.CO","DSV.CO","CARL-B.CO","COLO-B.CO","ORSTED.CO","ATCO-A.ST",
    "VOLV-B.ST","ERIC-B.ST","INVE-B.ST","SAND.ST","ASSA-B.ST","HM-B.ST",
    "EQNR","DNB.OL","NHY.OL","NOKIA.HE","SAMPO.HE","KNEBV.HE","FORTUM.HE",
    # Spagna
    "IBE.MC","SAN.MC","BBVA.MC","ITX.MC","TEF.MC","REP.MC","AMS.MC","CLNX.MC",
]

# ------------------------------------------------------------------ Asia
ASIA_SEED = [
    # Giappone
    "7203.T","6758.T","8306.T","6861.T","8035.T","6857.T","9983.T","9984.T",
    "7974.T","4063.T","6501.T","8058.T","8001.T","7267.T","6902.T","6981.T",
    "4568.T","4502.T","6273.T","6146.T","6920.T","6723.T","7741.T","4519.T",
    "8766.T","9433.T","9432.T","8316.T","6702.T","6367.T","6503.T","7011.T",
    # Corea
    "005930.KS","000660.KS","005380.KS","051910.KS","035420.KS","006400.KS",
    "000270.KS","068270.KS","105560.KS","055550.KS","012330.KS","028260.KS",
    # Taiwan (TSMC e UMC via ADR, vedi PREFER_ADR)
    "TSM","UMC","2454.TW","2317.TW","2308.TW","2382.TW","3711.TW","2881.TW",
    "2882.TW","2412.TW","1301.TW","2002.TW",
    # Hong Kong / Cina
    "0700.HK","BABA","3690.HK","1299.HK","0941.HK","1211.HK","1810.HK",
    "2318.HK","0939.HK","1398.HK","0388.HK","2020.HK","JD","NTES","1024.HK",
    "0981.HK","2331.HK","0016.HK","0027.HK","1929.HK",
    # India
    "RELIANCE.NS","TCS.NS","INFY","HDB","IBN","HINDUNILVR.NS","BHARTIARTL.NS",
    # Singapore / Australia
    "D05.SI","O39.SI","U11.SI","Z74.SI","CBA.AX","CSL.AX","WES.AX","NAB.AX",
    "FMG.AX","WDS.AX","BHP",
]

# dove esiste un ADR con dati migliori, il listino locale viene rimpiazzato
PREFER_ADR = {
    "2330.TW": "TSM", "2303.TW": "UMC", "ASML.AS": "ASML", "9988.HK": "BABA",
    "9618.HK": "JD", "9999.HK": "NTES", "NOVO-B.CO": "NVO",
    "STMPA.PA": "STM", "EQNR.OL": "EQNR", "0005.HK": "HSBA.L",
}

# ADR aggiunti d'ufficio all'universo (contati nella regione d'origine)
EXTRA_ADR = ["ASML", "NVO", "STM", "TSM", "UMC", "BABA", "JD", "NTES",
             "INFY", "HDB", "IBN", "BHP", "EQNR"]

# ------------------------------------------------- semiconduttori (flag)
SEMICONDUCTORS = {
    # USA
    "NVDA","AMD","INTC","TXN","QCOM","AVGO","MU","AMAT","LRCX","KLAC","ADI",
    "NXPI","ON","MRVL","MCHP","TER","SWKS","QRVO","GFS","MPWR","ARM","SMCI",
    "SNPS","CDNS",
    # Europa
    "ASML","STM","IFX.DE","BESI.AS","ASM.AS","NOKIA.HE",
    # Asia
    "TSM","UMC","005930.KS","000660.KS","2454.TW","8035.T","6857.T","6146.T",
    "6920.T","6723.T","4063.T","0981.HK","2308.TW","006400.KS",
}

_SUFFIX_REGION = {
    ".T": "Asia", ".KS": "Asia", ".KQ": "Asia", ".TW": "Asia", ".TWO": "Asia",
    ".HK": "Asia", ".NS": "Asia", ".BO": "Asia", ".SI": "Asia", ".AX": "Asia",
    ".PA": "Europa", ".MI": "Europa", ".DE": "Europa", ".AS": "Europa",
    ".BR": "Europa", ".SW": "Europa", ".L": "Europa", ".CO": "Europa",
    ".ST": "Europa", ".OL": "Europa", ".HE": "Europa", ".MC": "Europa",
}

# ADR che rappresentano società non USA
_ADR_REGION = {
    "ASML": "Europa", "NVO": "Europa", "STM": "Europa", "EQNR": "Europa",
    "TSM": "Asia", "UMC": "Asia", "BABA": "Asia", "JD": "Asia", "NTES": "Asia",
    "INFY": "Asia", "HDB": "Asia", "IBN": "Asia", "BHP": "Asia",
}


def region_of(ticker: str) -> str:
    if ticker in _ADR_REGION:
        return _ADR_REGION[ticker]
    for suffix, region in _SUFFIX_REGION.items():
        if ticker.endswith(suffix):
            return region
    return "USA"


def _fetch_sp500() -> list[str]:
    """Scarica i costituenti S&P 500 da Wikipedia. Richiede rete + lxml."""
    import pandas as pd
    tables = pd.read_html("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies")
    symbols = tables[0]["Symbol"].astype(str).str.replace(".", "-", regex=False)
    out = sorted(set(symbols.tolist()))
    if len(out) < 400:
        raise ValueError(f"lista S&P 500 sospetta: {len(out)} titoli")
    return out


def build_universe(verbose: bool = True) -> list[dict]:
    """Ritorna [{'ticker','region','semis'}] deduplicato, ADR preferiti."""
    try:
        us = _fetch_sp500()
        source = "Wikipedia"
    except Exception as exc:
        us = list(FALLBACK_US)
        source = f"fallback statico ({type(exc).__name__})"
    if verbose:
        print(f"  Universo USA: {len(us)} titoli [{source}]")

    raw = us + EUROPE_SEED + ASIA_SEED + EXTRA_ADR
    tickers, seen = [], set()
    for t in raw:
        t = PREFER_ADR.get(t, t)
        if t not in seen:
            seen.add(t)
            tickers.append(t)

    universe = [
        {"ticker": t, "region": region_of(t), "semis": t in SEMICONDUCTORS}
        for t in tickers
    ]
    if verbose:
        by_region = {}
        for row in universe:
            by_region[row["region"]] = by_region.get(row["region"], 0) + 1
        semis = sum(1 for r in universe if r["semis"])
        print(f"  Universo totale: {len(universe)} titoli — {by_region} — semiconduttori: {semis}")
    return universe
