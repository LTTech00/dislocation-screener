"""Dashboard HTML autonoma: nessun server, nessun CDN, doppio click e via.

Il file incorpora i dati come JSON; i pesi si regolano dal vivo e il ranking
si ricalcola nel browser. Un pannello in alto mostra sempre quanto sono
freschi i dati (la dashboard diventa rossa se sono vecchi)."""

from __future__ import annotations

import json
import math
from datetime import datetime

import pandas as pd


def _j(value, digits: int = 4):
    """Numero JSON-safe: None per NaN/inf, arrotondato."""
    try:
        if value is None:
            return None
        out = float(value)
        if math.isnan(out) or math.isinf(out):
            return None
        return round(out, digits)
    except (TypeError, ValueError):
        return None


def _spark(close: pd.Series | None, points: int = 53) -> list[float] | None:
    """Serie prezzi compattata per il grafico del dettaglio.

    Un anno di barre giornaliere sono ~252 punti per titolo: moltiplicati per
    l'universo gonfierebbero l'HTML di qualche megabyte. Campionando a passo
    costante restano ~53 punti (una lettura settimanale) — abbastanza per la
    forma della curva, che e' l'unica cosa che il grafico deve raccontare.
    L'ultima barra viene sempre inclusa: e' il prezzo che la tabella mostra.
    """
    if close is None or len(close) < 30:
        return None
    tail = close.dropna().tail(252)
    if len(tail) < 30:
        return None
    step = max(1, -(-len(tail) // points))      # ceil: mai piu' di `points`+1
    sampled = list(tail.iloc[::step])
    if sampled and sampled[-1] != tail.iloc[-1]:
        sampled.append(tail.iloc[-1])
    # Due decimali: il grafico e' alto 130px, la terza cifra non si vede e
    # moltiplicata per l'universo pesa piu' di quanto valga.
    out = [_j(v, 2) for v in sampled]
    return out if any(v is not None for v in out) else None


def rows_payload(df: pd.DataFrame, prices: dict | None = None) -> list[dict]:
    rows = []
    for _, r in df.iterrows():
        g = r.get
        ticker = g("ticker")
        px = None
        if prices:
            frame = prices.get(ticker)
            if frame is not None and "Close" in frame:
                px = _spark(frame["Close"])
        rows.append({
            "t": ticker,
            "n": g("name") or ticker,
            "r": g("region") or "USA",
            "s": g("sector") or "—",
            "semi": bool(g("semis")),
            "fin": bool(g("is_financial")),
            "sub": {
                "dislocation": _j(g("sub_dislocation"), 1),
                "quality": _j(g("sub_quality"), 1),
                "value": _j(g("sub_value"), 1),
                "repricing": _j(g("sub_repricing"), 1),
                "timing": _j(g("sub_timing"), 1),
            },
            "pen": _j(g("penalty_total"), 1) or 0,
            "penItems": [{"p": _j(i["points"], 1), "l": i["label"]}
                         for i in (g("penalty_items") or [])],
            "conf": _j(g("confidence"), 2),
            "m": {
                "price": _j(g("last_close"), 2),
                "priceDate": g("last_price_date"),
                "ccy": g("currency") or "",
                "mcapUsd": _j(g("market_cap_usd"), 0),
                "ret1m": _j(g("ret_1m")),
                "ret3m": _j(g("ret_3m")),
                "sig": _j(g("sigma_move_1m"), 2),
                "dd": _j(g("drawdown_52w")),
                "vol": _j(g("vol_annual"), 3),
                "rsi": _j(g("rsi_14"), 1),
                "days": _j(g("days_since_low_1m"), 0),
                "capr": _j(g("capitulation_ratio"), 1),
                "epsD30": _j(g("eps_d30")),
                "epsD90": _j(g("eps_d90")),
                "hasEst": bool(g("has_estimates")),
                "roic": _j(g("roic")),
                "roicTrend": _j(g("roic_trend")),
                "fcfConv": _j(g("fcf_conversion"), 2),
                "fcfY": _j(g("fcf_yield")),
                "evEbitda": _j(g("ev_ebitda"), 1),
                "fpe": _j(g("forward_pe"), 1),
                "pb": _j(g("price_to_book"), 2),
                "roe": _j(g("roe")),
                "ndEbitda": _j(g("net_debt_ebitda"), 2),
                "intCov": _j(g("interest_coverage"), 1),
                "revCagr": _j(g("revenue_cagr_3y")),
                "shortPct": _j(g("short_pct_float")),
            },
            "px": px,
            "news": g("news") if isinstance(g("news"), list) else [],
        })
    return rows


def build_html(rows: list[dict], meta: dict) -> str:
    payload = {"meta": meta, "rows": rows}
    data_json = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
    return _TEMPLATE.replace("__DATA_JSON__", data_json)


def write_report(df: pd.DataFrame, meta: dict, path: str,
                 prices: dict | None = None) -> None:
    html = build_html(rows_payload(df, prices), meta)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(html)


# ============================================================== TEMPLATE ==
_TEMPLATE = r"""<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Dislocation Screener</title>
<style>
:root{
  /* Tema chiaro da terminale finanziario: fondo bianco, grigi a bassa
     saturazione, filetti sottili invece di riquadri pieni. Il colore e'
     riservato al dato — se coloriamo anche la cornice, il dato non spicca. */
  --bg:#FFFFFF; --panel:#FFFFFF; --panel2:#F8FAFC; --line:#E2E8F0;
  --line-soft:#EFF3F7; --track:#E8EDF2;
  --text:#0F172A; --muted:#64748B; --faint:#657485;
  /* Tonalita' scelte per restare leggibili SU BIANCO: l'ambra e il verde
     accesi del tema scuro qui scenderebbero sotto il 4.5:1. Tutte queste
     finiscono anche come testo, quindi rispettano la soglia AA. */
  --dis:#7C3AED; --qua:#047857; --val:#0369A1; --rep:#B45309; --tim:#DB2777;
  --danger:#B42318; --ok:#067647; --warn:#B45309;
  --sans:system-ui,-apple-system,"Segoe UI",Roboto,"Helvetica Neue",sans-serif;
  --mono:ui-monospace,"SF Mono","Cascadia Mono",Consolas,Menlo,monospace;
  --shadow:0 1px 2px rgba(15,23,42,.04);
}
*{box-sizing:border-box;margin:0}
html{scrollbar-color:#CBD5E1 #F1F5F9}
body{background:var(--bg);color:var(--text);font-family:var(--sans);
  font-size:14px;line-height:1.45;-webkit-font-smoothing:antialiased}
a{color:var(--val);text-decoration:none}
a:hover{text-decoration:underline}
.wrap{max-width:1280px;margin:0 auto;padding:20px 22px 60px}
.num{font-family:var(--mono);font-variant-numeric:tabular-nums}

/* ---------- banner stato dati ---------- */
#banner{display:none;padding:10px 22px;font-weight:600;text-align:center;font-size:13px}
#banner.red{display:block;background:#FEF2F2;color:#991B1B;border-bottom:1px solid #FECACA}
#banner.amber{display:block;background:#FFFBEB;color:#92400E;border-bottom:1px solid #FDE68A}

/* ---------- testata ---------- */
header.mast{display:flex;flex-wrap:wrap;gap:16px;align-items:flex-end;
  justify-content:space-between;padding:6px 0 18px;border-bottom:1px solid var(--line)}
.wordmark{display:flex;align-items:center;gap:9px;font-size:15px;
  letter-spacing:.16em;text-transform:uppercase;font-weight:600}
.wordmark::before{content:"";width:9px;height:16px;background:var(--text);
  border-radius:1px;flex:none}
.tagline{color:var(--muted);margin-top:4px;font-size:13px}
.fresh{background:var(--panel2);border:1px solid var(--line);border-radius:8px;
  padding:10px 14px;min-width:280px}
.fresh .row1{display:flex;align-items:center;gap:8px;font-weight:600}
.dot{width:9px;height:9px;border-radius:50%;background:var(--ok);flex:none}
.dot.amber{background:var(--warn)} .dot.red{background:var(--danger)}
.fresh .row2{color:var(--muted);font-size:12px;margin-top:4px}

/* ---------- controlli ---------- */
.controls{display:flex;flex-wrap:wrap;gap:12px;align-items:stretch;margin:16px 0 8px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:8px;
  padding:12px 14px;box-shadow:var(--shadow)}
.card h3{font-size:11px;letter-spacing:.1em;text-transform:uppercase;
  color:var(--faint);margin-bottom:8px;font-weight:600}
.weights{flex:1 1 460px}
.wgrid{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:8px 16px}
.wrow{display:grid;grid-template-columns:1fr auto;gap:2px 8px;align-items:center}
.wrow label{font-size:12px;color:var(--muted);display:flex;align-items:center;gap:6px}
.swatch{width:8px;height:8px;border-radius:2px;display:inline-block}
.wrow output{font-family:var(--mono);font-size:12px}
.wrow input[type=range]{grid-column:1/3;width:100%;accent-color:var(--rep);height:18px}
.reset{margin-top:8px;background:none;border:1px solid var(--line);color:var(--muted);
  border-radius:6px;padding:4px 10px;font-size:12px;cursor:pointer}
.reset:hover{color:var(--text);border-color:var(--faint);background:var(--panel2)}
.filters{flex:1 1 380px;display:flex;flex-direction:column;gap:10px}
.chiprow{display:flex;flex-wrap:wrap;gap:6px}
.chip{border:1px solid var(--line);border-radius:999px;padding:4px 12px;
  color:var(--muted);cursor:pointer;background:none;font-size:12.5px}
.chip.on{color:var(--bg);background:var(--text);border-color:var(--text);font-weight:600}
.chip.semi.on{background:var(--rep);border-color:var(--rep)}
.frow{display:flex;gap:8px;flex-wrap:wrap;align-items:center}
select,input[type=search]{background:var(--panel2);border:1px solid var(--line);
  color:var(--text);border-radius:6px;padding:6px 8px;font-size:13px}
input[type=search]{flex:1;min-width:140px}
.conf{display:flex;align-items:center;gap:8px;color:var(--muted);font-size:12px}
.conf input{accent-color:var(--val)}

/* ---------- tabella ---------- */
.counts{color:var(--muted);font-size:12.5px;margin:10px 2px}
.counts b{color:var(--text)}
.table-wrap{overflow-x:auto;border:1px solid var(--line);border-radius:8px;
  background:var(--panel);box-shadow:var(--shadow)}
table{border-collapse:collapse;width:100%;min-width:960px}
thead th{position:sticky;top:0;background:var(--panel2);color:var(--muted);
  font-size:10.5px;letter-spacing:.09em;text-transform:uppercase;text-align:left;
  padding:9px 10px;border-bottom:1px solid var(--line);white-space:nowrap;
  cursor:pointer;transition:color .15s}
thead th:hover{color:var(--text)}
thead th.num-h{text-align:right}
tbody td{padding:7px 10px;border-bottom:1px solid var(--line-soft);vertical-align:middle}
tbody tr{cursor:pointer;transition:background .12s}
tbody tr:hover{background:#F5F8FB}
tbody tr:focus-visible{outline:2px solid var(--val);outline-offset:-2px}
td.rank{color:var(--faint);font-family:var(--mono);width:34px}
.name b{display:block;font-weight:600;max-width:250px;overflow:hidden;
  text-overflow:ellipsis;white-space:nowrap}
.name span{color:var(--faint);font-family:var(--mono);font-size:11.5px}
.badge{font-size:10px;border:1px solid var(--line);border-radius:4px;
  padding:1px 5px;color:var(--muted);margin-left:6px;letter-spacing:.05em}
.badge.semi{color:var(--rep);border-color:#FCD9A6;background:#FFFBEB}
.sector{color:var(--muted);font-size:12px;max-width:150px;overflow:hidden;
  text-overflow:ellipsis;white-space:nowrap}
td.right{text-align:right}
.spine{display:flex;height:8px;width:130px;background:var(--track);border-radius:2px;overflow:hidden}
.spine i{display:block;height:100%}
.scorechip{font-family:var(--mono);font-weight:700;font-size:14px;
  padding:2px 8px;border-radius:5px;background:var(--panel2);border:1px solid var(--line);
  display:inline-block;min-width:46px;text-align:right}
.neg{color:var(--danger)}.pos{color:var(--ok)}
.gapcell{font-family:var(--mono)}
.gapcell.big{color:var(--rep);font-weight:700}
.confbar{width:44px;height:5px;background:var(--track);border-radius:3px;display:inline-block;vertical-align:middle}
.confbar i{display:block;height:100%;border-radius:3px;background:var(--faint)}
.empty{padding:40px;text-align:center;color:var(--muted)}

/* ---------- drawer ---------- */
#backdrop{position:fixed;inset:0;background:rgba(15,23,42,.28);opacity:0;
  pointer-events:none;transition:opacity .18s}
#backdrop.on{opacity:1;pointer-events:auto}
#drawer{position:fixed;top:0;right:0;bottom:0;width:min(540px,100vw);
  background:var(--panel);border-left:1px solid var(--line);
  box-shadow:-8px 0 24px rgba(15,23,42,.08);
  transform:translateX(102%);transition:transform .2s ease;overflow-y:auto;z-index:10}
#drawer.on{transform:none}
.dhead{padding:18px 20px 14px;border-bottom:1px solid var(--line);
  position:sticky;top:0;background:var(--panel);z-index:2}
.dhead .close{position:absolute;top:14px;right:14px;background:none;border:none;
  color:var(--muted);font-size:20px;cursor:pointer;line-height:1}
.dhead h2{font-size:19px;font-weight:600;letter-spacing:-.01em;padding-right:76px}
.dhead .sub{padding-right:76px}
.dhead .sub{color:var(--muted);font-size:12.5px;margin-top:3px}
.dhead .bigscore{position:absolute;right:18px;top:44px;font-family:var(--mono);
  font-size:26px;font-weight:700}
.dlinks{display:flex;gap:14px;margin-top:10px;font-size:12.5px}
.dbody{padding:16px 20px 30px;display:flex;flex-direction:column;gap:20px}
.dsec h4{font-size:11px;letter-spacing:.1em;text-transform:uppercase;
  color:var(--faint);margin-bottom:10px}

/* grafico dello scarto */
.gapchart{background:var(--panel2);border:1px solid var(--line);border-radius:8px;padding:14px}
.gbar{position:relative;height:22px;margin:7px 0}
.gbar .lbl{position:absolute;left:0;top:0;bottom:0;display:flex;align-items:center;
  font-size:11.5px;color:var(--muted);width:96px}
.gtrack{position:absolute;left:100px;right:0;top:3px;bottom:3px}
.gzero{position:absolute;top:-6px;bottom:-6px;width:1px;background:var(--faint)}
.gfill{position:absolute;top:0;bottom:0;border-radius:3px}
.gval{position:absolute;top:0;bottom:0;display:flex;align-items:center;
  font-family:var(--mono);font-size:12px;padding:0 6px;white-space:nowrap}
.gapband{position:relative;height:16px;margin:2px 0 4px}
.gapband .zone{position:absolute;top:2px;bottom:2px;border-radius:2px;
  background:repeating-linear-gradient(135deg,rgba(180,83,9,.22) 0 4px,transparent 4px 8px);
  border:1px dashed var(--rep)}
.gaplegend{color:var(--muted);font-size:12px;margin-top:8px}
.gaplegend b{color:var(--rep);font-family:var(--mono)}
.gapnote{margin-top:6px;font-size:12px;color:var(--muted)}
.gapnote.alert{color:var(--danger)}

/* grafico prezzo — SVG disegnato a mano, nessuna libreria esterna */
.pxchart{background:var(--panel2);border:1px solid var(--line);border-radius:8px;padding:12px 14px}
.pxhead{display:flex;justify-content:space-between;align-items:baseline;gap:12px}
.pxlast{font-family:var(--mono);font-size:19px;font-weight:600;letter-spacing:-.02em}
.pxccy{color:var(--muted);font-size:12px;font-weight:400;margin-left:3px}
.pxchg{font-family:var(--mono);font-size:12.5px;font-weight:600}
.pxsvg{display:block;width:100%;height:132px;margin:10px 0 2px}
.pxsvg path,.pxsvg line{vector-effect:non-scaling-stroke}
.pxmeta{display:flex;justify-content:space-between;font-family:var(--mono);
  font-size:11px;color:var(--faint)}
.pxnote{color:var(--muted);font-size:11.5px;margin-top:7px;
  padding-top:7px;border-top:1px solid var(--line)}
.pxnodata{color:var(--muted);font-size:12.5px}

/* assi */
.axrow{display:grid;grid-template-columns:96px 1fr 78px;gap:10px;
  align-items:center;margin:7px 0;font-size:12.5px}
.axrow .bar{height:8px;background:var(--track);border-radius:2px;overflow:hidden}
.axrow .bar i{display:block;height:100%}
.axrow .v{font-family:var(--mono);color:var(--muted);text-align:right}

/* fondamentali */
.fgrid{display:grid;grid-template-columns:1fr 1fr;gap:7px 18px}
.fitem{display:flex;justify-content:space-between;gap:8px;border-bottom:1px solid var(--line-soft);
  padding:4px 0;font-size:12.5px}
.fitem span{color:var(--muted)} .fitem b{font-family:var(--mono);font-weight:600}

.penlist{display:flex;flex-direction:column;gap:6px}
.pen{display:flex;gap:8px;align-items:baseline;font-size:12.5px;color:var(--danger)}
.pen b{font-family:var(--mono);flex:none}
.nopen{color:var(--muted);font-size:12.5px}

.newslist{display:flex;flex-direction:column;gap:10px}
.newsitem a{color:var(--text);font-size:13px;display:block}
.newsitem .src{color:var(--faint);font-size:11.5px;margin-top:1px}

footer{margin-top:34px;padding-top:16px;border-top:1px solid var(--line);
  color:var(--faint);font-size:12px;max-width:900px}
footer b{color:var(--muted)}

@media (prefers-reduced-motion: reduce){
  *{transition:none!important;animation:none!important}
}
@media (max-width:720px){
  .wordmark{font-size:21px}
  .fresh{min-width:0;width:100%}
}
</style>
</head>
<body>
<div id="banner"></div>
<div class="wrap">

<header class="mast">
  <div>
    <div class="wordmark">Dislocation Screener</div>
    <div class="tagline">Qualità il cui prezzo è sceso più delle stime sugli utili.</div>
  </div>
  <div class="fresh" id="fresh">
    <div class="row1"><span class="dot" id="freshdot"></span><span id="freshtitle"></span></div>
    <div class="row2" id="freshdetail"></div>
  </div>
</header>

<div class="controls">
  <div class="card weights">
    <h3>Pesi degli assi — il ranking si ricalcola dal vivo</h3>
    <div class="wgrid" id="wgrid"></div>
    <button class="reset" id="wreset">Ripristina i pesi di default</button>
  </div>
  <div class="card filters">
    <h3>Filtri</h3>
    <div class="chiprow" id="regions"></div>
    <div class="frow">
      <select id="sector"><option value="">Tutti i settori</option></select>
      <button class="chip semi" id="semitoggle">Solo semiconduttori</button>
    </div>
    <div class="frow">
      <input type="search" id="search" placeholder="Cerca nome o ticker…">
    </div>
    <div class="conf">Confidenza dati minima
      <input type="range" id="confmin" min="0" max="90" step="5" value="0">
      <output id="confout" class="num">0%</output>
    </div>
  </div>
</div>

<div class="counts" id="counts"></div>

<div class="table-wrap">
<table>
  <thead><tr>
    <th>#</th><th>Società</th><th>Settore</th><th>Profilo</th>
    <th class="num-h">Score</th><th class="num-h">σ&nbsp;1M</th>
    <th class="num-h">1M&nbsp;%</th><th class="num-h">Scarto&nbsp;30g</th>
    <th class="num-h">Conf.</th>
  </tr></thead>
  <tbody id="tbody"></tbody>
</table>
<div class="empty" id="emptymsg" style="display:none"></div>
</div>

<footer>
  <b>Strumento didattico.</b> Produce candidati da analizzare a mano, non
  raccomandazioni di investimento. Uno score alto significa solo che il titolo
  assomiglia a un profilo statistico calcolato su dati gratuiti che possono
  essere incompleti, in ritardo o errati. Lo screener non conosce il motivo del
  calo: leggere le notizie e i bilanci resta compito tuo, e ogni decisione
  operativa avviene fuori da qui, sul tuo broker, a tuo rischio.
</footer>
</div>

<div id="backdrop"></div>
<aside id="drawer" aria-hidden="true"></aside>

<script id="data" type="application/json">__DATA_JSON__</script>
<script>
"use strict";
const DATA = JSON.parse(document.getElementById("data").textContent);
const META = DATA.meta, ROWS = DATA.rows;
const AXES = [
  ["dislocation","Dislocazione","--dis"],
  ["quality","Qualità","--qua"],
  ["value","Valore","--val"],
  ["repricing","Repricing gap","--rep"],
  ["timing","Timing","--tim"],
];
const css = v => getComputedStyle(document.documentElement).getPropertyValue(v).trim();
const esc = s => String(s ?? "").replace(/[&<>"']/g,
  c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const nf1 = new Intl.NumberFormat("it-IT",{minimumFractionDigits:1,maximumFractionDigits:1});
const nf2 = new Intl.NumberFormat("it-IT",{maximumFractionDigits:2});
const pct = (v,d=1) => v==null ? "—" :
  (v>0?"+":"") + new Intl.NumberFormat("it-IT",{minimumFractionDigits:d,maximumFractionDigits:d}).format(v*100) + "%";
const num = (v,d=1) => v==null ? "—" : new Intl.NumberFormat("it-IT",{minimumFractionDigits:d,maximumFractionDigits:d}).format(v);
const mcap = v => v==null ? "—" : v>=1e12 ? nf2.format(v/1e12)+" T$" : nf2.format(v/1e9)+" mld $";

/* ------------------------------------------------ stato */
let weights = Object.assign({}, META.weightsDefault);
let filt = {region:"Tutti", semi:false, sector:"", q:"", conf:0};
let sortKey = "score", sortDir = -1;

/* ------------------------------------------------ freschezza dati */
function freshness(){
  const dot = document.getElementById("freshdot");
  const title = document.getElementById("freshtitle");
  const det = document.getElementById("freshdetail");
  const banner = document.getElementById("banner");
  const gen = new Date(META.generatedAt);
  const ageH = (Date.now() - gen.getTime())/3.6e6;
  const dfmt = new Intl.DateTimeFormat("it-IT",{day:"2-digit",month:"short",year:"numeric"});
  const tfmt = new Intl.DateTimeFormat("it-IT",{day:"2-digit",month:"short",hour:"2-digit",minute:"2-digit"});
  if (META.synthetic){
    dot.className = "dot red";
    title.textContent = "DATI SINTETICI — anteprima della sola interfaccia";
    det.textContent = "Nomi e numeri generati a caso. Per i dati reali: python -m screener.run_screen";
    banner.className = "red";
    banner.textContent = "⚠ ANTEPRIMA CON DATI SINTETICI — nessun numero in questa pagina è reale";
    return;
  }
  title.textContent = "Dati aggiornati al " + tfmt.format(gen);
  const bits = [];
  if (META.pricesDate) bits.push("prezzi al " + dfmt.format(new Date(META.pricesDate)));
  if (META.fundAgeMedianDays!=null) bits.push("fondamentali ~" + Math.round(META.fundAgeMedianDays) + "g");
  if (META.estCoveragePct!=null) bits.push("stime coperte " + Math.round(META.estCoveragePct) + "%");
  bits.push(META.fxFresh ? "FX ok" : "FX di riserva");
  det.textContent = bits.join(" · ");
  if (ageH > 72){
    dot.className = "dot red";
    banner.className = "red";
    banner.textContent = "⚠ Dati vecchi di " + Math.round(ageH/24) +
      " giorni — rilancia: python -m screener.run_screen";
  } else if (ageH > 26){
    dot.className = "dot amber";
    banner.className = "amber";
    banner.textContent = "Dati di " + Math.round(ageH/24) +
      " giorno/i fa — per aggiornare: python -m screener.run_screen";
  }
}

/* ------------------------------------------------ scoring dal vivo */
function scoreOf(row){
  let num = 0, den = 0;
  for (const [k] of AXES){
    const w = weights[k] || 0;
    const s = row.sub[k] == null ? 35 : row.sub[k];
    num += w*s; den += w;
  }
  if (!den) return 0;
  return Math.max(0, Math.min(100, num/den - row.pen));
}

/* ------------------------------------------------ controlli pesi */
function buildWeights(){
  const grid = document.getElementById("wgrid");
  grid.innerHTML = "";
  for (const [key,label,varname] of AXES){
    const div = document.createElement("div");
    div.className = "wrow";
    div.innerHTML = `<label><span class="swatch" style="background:var(${varname})"></span>${label}</label>
      <output class="num">${weights[key]}</output>
      <input type="range" min="0" max="40" step="1" value="${weights[key]}" data-k="${key}">`;
    const input = div.querySelector("input"), out = div.querySelector("output");
    input.addEventListener("input", () => {
      weights[key] = +input.value; out.textContent = input.value; render();
    });
    grid.appendChild(div);
  }
  document.getElementById("wreset").onclick = () => {
    weights = Object.assign({}, META.weightsDefault); buildWeights(); render();
  };
}

/* ------------------------------------------------ filtri */
function buildFilters(){
  const regions = ["Tutti","USA","Europa","Asia"];
  const box = document.getElementById("regions");
  regions.forEach(r => {
    const b = document.createElement("button");
    b.className = "chip" + (r===filt.region ? " on" : "");
    b.textContent = r;
    b.onclick = () => { filt.region = r;
      box.querySelectorAll(".chip").forEach(c=>c.classList.toggle("on", c===b));
      render(); };
    box.appendChild(b);
  });
  const sectors = [...new Set(ROWS.map(r=>r.s).filter(s=>s && s!=="—"))].sort();
  const sel = document.getElementById("sector");
  sectors.forEach(s => { const o=document.createElement("option"); o.value=o.textContent=s; sel.appendChild(o); });
  sel.onchange = () => { filt.sector = sel.value; render(); };
  const semi = document.getElementById("semitoggle");
  semi.onclick = () => { filt.semi=!filt.semi; semi.classList.toggle("on", filt.semi); render(); };
  const search = document.getElementById("search");
  search.oninput = () => { filt.q = search.value.trim().toLowerCase(); render(); };
  const conf = document.getElementById("confmin"), confout=document.getElementById("confout");
  conf.oninput = () => { filt.conf = +conf.value/100; confout.textContent = conf.value+"%"; render(); };
  document.querySelectorAll("thead th").forEach((th,i)=>{
    const keys = [null,"n","s",null,"score","sig","ret1m","gap","conf"];
    if(!keys[i]) return;
    th.onclick = () => { const k=keys[i];
      if (sortKey===k) sortDir*=-1; else {sortKey=k; sortDir = (k==="n"||k==="s")?1:-1;}
      render(); };
  });
}

function gapOf(r){
  if (!r.m.hasEst || r.m.ret1m==null || r.m.epsD30==null) return null;
  return (r.m.ret1m - r.m.epsD30) * 100;   // punti percentuali
}

/* ------------------------------------------------ tabella */
function spine(row){
  let total = 0; const segs = [];
  for (const [k,label,varname] of AXES){
    const w = weights[k]||0, s = row.sub[k]==null?35:row.sub[k];
    const part = w*s; total += w*100;
    segs.push([part, varname, label, row.sub[k]]);
  }
  return `<div class="spine" title="${segs.map(s=>`${s[2]}: ${s[3]==null?"n.d.":nf1.format(s[3])}`).join(" · ")}">` +
    segs.map(([part,varname]) =>
      `<i style="width:${total? (part/total*100):0}%;background:var(${varname})"></i>`).join("") +
    `</div>`;
}

function visibleRows(){
  return ROWS
    .map(r => Object.assign({_score: scoreOf(r), _gap: gapOf(r)}, r))
    .filter(r =>
      (filt.region==="Tutti" || r.r===filt.region) &&
      (!filt.semi || r.semi) &&
      (!filt.sector || r.s===filt.sector) &&
      (r.conf==null || r.conf >= filt.conf) &&
      (!filt.q || r.n.toLowerCase().includes(filt.q) || r.t.toLowerCase().includes(filt.q)));
}

function render(){
  const rows = visibleRows();
  const mapping = {score:"_score", gap:"_gap", n:"n", s:"s", conf:"conf"};
  rows.sort((a,b)=>{
    let va, vb;
    if (sortKey in mapping){ va = a[mapping[sortKey]]; vb = b[mapping[sortKey]]; }
    else { va = a.m[sortKey]; vb = b.m[sortKey]; }
    if (typeof va==="string") return va.localeCompare(vb)*sortDir;
    va = va==null?-1e9:va; vb = vb==null?-1e9:vb;
    return (va-vb)*sortDir;
  });
  const top = rows.slice(0,100);
  const tbody = document.getElementById("tbody");
  document.getElementById("counts").innerHTML =
    `<b>${rows.length}</b> titoli oltre il trigger di dislocazione con i filtri attuali ` +
    `(universo analizzato: ${META.universeCount ?? "—"} · dopo le esclusioni: ${META.gatedCount ?? "—"}) — mostrati i primi ${top.length}.`;
  document.getElementById("emptymsg").style.display = top.length ? "none":"block";
  document.getElementById("emptymsg").textContent =
    "Nessun titolo con questi filtri. In un mercato calmo è normale: significa che non ci sono dislocazioni, non che lo screen è rotto.";
  tbody.innerHTML = top.map((r,i)=>{
    const gap = r._gap;
    const gapCls = gap!=null && gap < -8 ? "gapcell big" : "gapcell";
    return `<tr data-t="${esc(r.t)}">
      <td class="rank">${i+1}</td>
      <td class="name"><b>${esc(r.n)}</b><span>${esc(r.t)}</span>
        <span class="badge">${esc(r.r)}</span>${r.semi?'<span class="badge semi">SEMI</span>':""}</td>
      <td class="sector">${esc(r.s)}</td>
      <td>${spine(r)}</td>
      <td class="right"><span class="scorechip">${nf1.format(r._score)}</span></td>
      <td class="right num">${r.m.sig==null?"—":nf1.format(r.m.sig)+"σ"}</td>
      <td class="right num ${r.m.ret1m<0?"neg":"pos"}">${pct(r.m.ret1m)}</td>
      <td class="right ${gapCls}">${gap==null?"—":(gap>0?"+":"")+nf1.format(gap)+" pt"}</td>
      <td class="right"><span class="confbar"><i style="width:${(r.conf??0)*100}%"></i></span></td>
    </tr>`;
  }).join("");
  tbody.querySelectorAll("tr").forEach(tr =>
    tr.onclick = () => openDrawer(tr.dataset.t));
}

/* ------------------------------------------------ drawer di dettaglio */
/* Grafico prezzo a 12 mesi. SVG costruito a mano: la dashboard deve
   restare un file solo, apribile con doppio click e senza rete, quindi
   niente Chart.js e niente CDN. viewBox fisso + preserveAspectRatio="none"
   lo fa allungare alla larghezza del drawer; vector-effect tiene il tratto
   di spessore costante malgrado lo stiramento. */
function pxChart(r){
  const px = (r.px || []).filter(v => v != null);
  if (px.length < 8)
    return `<div class="pxchart"><div class="pxnodata">Serie storica non disponibile
      per questo titolo.</div></div>`;
  const lo = Math.min(...px), hi = Math.max(...px);
  const span = (hi - lo) || 1;
  const W = 300, H = 100, pad = 7;
  const X = i => (i / (px.length - 1)) * W;
  const Y = v => pad + (1 - (v - lo) / span) * (H - 2 * pad);

  let d = "";
  px.forEach((v, i) => { d += (i ? "L" : "M") + X(i).toFixed(1) + " " + Y(v).toFixed(1); });
  const area = d + `L${W} ${H} L0 ${H} Z`;

  const last = px[px.length - 1], first = px[0];
  const chg = (last / first - 1) * 100;
  const col = chg >= 0 ? "var(--ok)" : "var(--danger)";
  /* Campionamento settimanale: le ultime ~4 letture sono l'ultimo mese,
     cioe' la finestra su cui scatta il trigger di dislocazione. */
  const i1m = Math.max(0, px.length - 5);
  const yHi = Y(hi).toFixed(1), yLo = Y(lo).toFixed(1);

  return `<div class="pxchart">
    <div class="pxhead">
      <div><span class="pxlast">${nf2.format(last)}</span><span class="pxccy">${esc(r.m.ccy||"")}</span></div>
      <div class="pxchg" style="color:${col}">${(chg>=0?"+":"")+nf1.format(chg)}% · 12 mesi</div>
    </div>
    <svg class="pxsvg" viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" role="img"
         aria-label="Andamento del prezzo negli ultimi dodici mesi">
      <defs><linearGradient id="pxg" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stop-color="${col}" stop-opacity=".16"/>
        <stop offset="100%" stop-color="${col}" stop-opacity="0"/>
      </linearGradient></defs>
      <rect x="${X(i1m).toFixed(1)}" y="0" width="${(W-X(i1m)).toFixed(1)}" height="${H}"
            fill="var(--track)" opacity=".55"/>
      <line x1="0" y1="${yHi}" x2="${W}" y2="${yHi}" stroke="var(--line)"
            stroke-width="1" stroke-dasharray="3 3"/>
      <line x1="0" y1="${yLo}" x2="${W}" y2="${yLo}" stroke="var(--line)"
            stroke-width="1" stroke-dasharray="3 3"/>
      <path d="${area}" fill="url(#pxg)"/>
      <path d="${d}" fill="none" stroke="${col}" stroke-width="1.6"
            stroke-linejoin="round" stroke-linecap="round"/>
    </svg>
    <div class="pxmeta"><span>min ${nf2.format(lo)}</span><span>max ${nf2.format(hi)}</span></div>
    <div class="pxnote">La fascia grigia a destra e' l'ultimo mese, la finestra su cui
      scatta il trigger. Righe tratteggiate: minimo e massimo del periodo.</div>
  </div>`;
}

function gapChart(r){
  const dp = r.m.ret1m==null?null:r.m.ret1m*100;
  const de = !r.m.hasEst||r.m.epsD30==null?null:r.m.epsD30*100;
  if (dp==null) return "";
  const vals = [dp, de??0, 0];
  const lo = Math.min(...vals), hi = Math.max(...vals);
  const span = Math.max(6, hi-lo) * 1.15;
  const x = v => ((v - (lo - span*0.06)) / span) * 100;   // percento nel track
  const bar = (label, v, color) => {
    if (v==null) return `<div class="gbar"><div class="lbl">${label}</div>
      <div class="gtrack"><div class="gzero" style="left:${x(0)}%"></div>
      <div class="gval" style="left:${x(0)}%">n.d.</div></div></div>`;
    const l = Math.min(x(0), x(v)), w = Math.abs(x(v)-x(0));
    return `<div class="gbar"><div class="lbl">${label}</div>
      <div class="gtrack">
        <div class="gzero" style="left:${x(0)}%"></div>
        <div class="gfill" style="left:${l}%;width:${w}%;background:${color}"></div>
        <div class="gval" style="left:${Math.max(x(v),x(0))+.5}%">${(v>0?"+":"")+nf1.format(v)}%</div>
      </div></div>`;
  };
  let band = "", legend = "";
  if (de!=null){
    const gl = Math.min(x(dp), x(de)), gw = Math.abs(x(dp)-x(de));
    band = `<div class="gapband"><div style="position:absolute;left:100px;right:0;top:0;bottom:0">
      <div class="zone" style="left:${gl}%;width:${gw}%"></div></div></div>`;
    const gap = dp - de;
    legend = `<div class="gaplegend">La banda tratteggiata è la tesi — scarto:
      <b>${(gap>0?"+":"")+nf1.format(gap)} pt</b> ${gap<0?"(il prezzo è sceso più delle stime)":""}</div>`;
  } else {
    legend = `<div class="gaplegend">Stime di consenso non disponibili: lo scarto non è calcolabile.</div>`;
  }
  let note = "";
  if (r.m.epsD90!=null && r.m.epsD90 < META.collapseThreshold)
    note = `<div class="gapnote alert">Attenzione: stime FY+1 giù del ${nf1.format(r.m.epsD90*100)}% in 90 giorni.
      Qui il mercato sta probabilmente riprezzando a ragione (post-earnings drift), non sbagliando.</div>`;
  else if (r.m.epsD90!=null)
    note = `<div class="gapnote">Stime a 90 giorni: ${pct(r.m.epsD90)}.</div>`;
  return `<div class="gapchart">
    ${bar("Prezzo 1M", dp, "var(--danger)")}
    ${band}
    ${bar("Stime EPS 30g", de, "var(--val)")}
    ${legend}${note}</div>`;
}

function fitem(label, value){
  return `<div class="fitem"><span>${label}</span><b>${value}</b></div>`;
}

function openDrawer(t){
  const r = ROWS.find(x=>x.t===t); if (!r) return;
  const drawer = document.getElementById("drawer");
  const score = scoreOf(r);
  const yurl = "https://finance.yahoo.com/quote/" + encodeURIComponent(r.t);
  const gurl = "https://news.google.com/search?q=" + encodeURIComponent(r.n + " stock");
  const axes = AXES.map(([k,label,varname])=>{
    const v = r.sub[k];
    return `<div class="axrow"><span>${label}</span>
      <div class="bar"><i style="width:${v??0}%;background:var(${varname})"></i></div>
      <span class="v">${v==null?"n.d.":nf1.format(v)} · ×${weights[k]}</span></div>`;
  }).join("");
  const pens = r.penItems.length
    ? `<div class="penlist">` + r.penItems.map(p =>
        `<div class="pen"><b>−${nf1.format(p.p)}</b><span>${esc(p.l)}</span></div>`).join("") + `</div>`
    : `<div class="nopen">Nessuna penalità.</div>`;
  const isFin = r.fin;
  const fg = [
    fitem("Prezzo", r.m.price==null?"—":nf2.format(r.m.price)+" "+esc(r.m.ccy)+(r.m.priceDate?" · "+r.m.priceDate:"")),
    fitem("Capitalizzazione", mcap(r.m.mcapUsd)),
    fitem("ROIC", pct(r.m.roic)),
    fitem("Trend ROIC 3A", r.m.roicTrend==null?"—":(r.m.roicTrend>0?"in salita":"in calo")),
    isFin ? fitem("ROE", pct(r.m.roe)) : fitem("Conversione FCF", num(r.m.fcfConv,2)+"×"),
    isFin ? fitem("P/B", num(r.m.pb,2)) : fitem("EV/EBITDA", num(r.m.evEbitda,1)+"×"),
    fitem("P/E forward", num(r.m.fpe,1)+"×"),
    isFin ? "" : fitem("FCF yield", pct(r.m.fcfY)),
    isFin ? "" : fitem("Net debt/EBITDA", num(r.m.ndEbitda,2)+"×"),
    isFin ? "" : fitem("Copertura interessi", num(r.m.intCov,1)+"×"),
    fitem("CAGR ricavi 3A", pct(r.m.revCagr)),
    fitem("Short interest", pct(r.m.shortPct)),
    fitem("Volatilità annua", pct(r.m.vol,0)),
    fitem("Drawdown 52 sett.", pct(r.m.dd)),
    fitem("RSI 14", num(r.m.rsi,0)),
    fitem("Giorni dal minimo 1M", r.m.days==null?"—":r.m.days),
    fitem("Vol. capitolazione", r.m.capr==null?"—":num(r.m.capr,1)+"× media"),
    fitem("Confidenza dati", r.conf==null?"—":Math.round(r.conf*100)+"%"),
  ].join("");
  const news = (r.news && r.news.length)
    ? `<div class="newslist">` + r.news.map(n =>
        `<div class="newsitem"><a href="${esc(n.link)}" target="_blank" rel="noopener">${esc(n.title)}</a>
         <div class="src">${esc(n.publisher)}${n.date? " · "+esc(n.date):""}</div></div>`).join("") + `</div>`
    : `<div class="nopen">Nessuna notizia in cache per questo titolo. Usa il link «Perché è sceso» qui sopra.</div>`;

  drawer.innerHTML = `
    <div class="dhead">
      <button class="close" aria-label="Chiudi">×</button>
      <h2>${esc(r.n)}</h2>
      <div class="sub"><span class="num">${esc(r.t)}</span> · ${esc(r.r)} · ${esc(r.s)}${r.semi?" · Semiconduttori":""}</div>
      <div class="bigscore">${nf1.format(score)}</div>
      <div class="dlinks">
        <a href="${gurl}" target="_blank" rel="noopener">Perché è sceso → notizie</a>
        <a href="${yurl}" target="_blank" rel="noopener">Scheda Yahoo Finance</a>
      </div>
    </div>
    <div class="dbody">
      <div class="dsec"><h4>Prezzo — ultimi 12 mesi</h4>${pxChart(r)}</div>
      <div class="dsec"><h4>Lo scarto — prezzo contro stime</h4>${gapChart(r)}</div>
      <div class="dsec"><h4>Contributo degli assi (pesi attuali)</h4>${axes}</div>
      <div class="dsec"><h4>Penalità (−${nf1.format(r.pen)} totali)</h4>${pens}</div>
      <div class="dsec"><h4>Numeri chiave</h4><div class="fgrid">${fg}</div></div>
      <div class="dsec"><h4>Ultime notizie</h4>${news}</div>
    </div>`;
  drawer.querySelector(".close").onclick = closeDrawer;
  drawer.classList.add("on");
  document.getElementById("backdrop").classList.add("on");
  drawer.setAttribute("aria-hidden","false");
}
function closeDrawer(){
  document.getElementById("drawer").classList.remove("on");
  document.getElementById("backdrop").classList.remove("on");
  document.getElementById("drawer").setAttribute("aria-hidden","true");
}
document.getElementById("backdrop").onclick = closeDrawer;
document.addEventListener("keydown", e => { if (e.key==="Escape") closeDrawer(); });

freshness();
buildWeights();
buildFilters();
render();
</script>
</body>
</html>
"""
