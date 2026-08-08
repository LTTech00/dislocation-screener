"""Test rapido offline: scoring e report devono girare senza rete.

  python -m screener.selftest
"""
import sys
sys.path.insert(0, ".")
from make_preview import build_synthetic
from screener import scoring, report, config

df = build_synthetic(seed=3)
scored = scoring.score_universe(df)
assert scored["score"].notna().all(), "score con NaN"
assert scored["score"].between(0, 100).all(), "score fuori scala"
assert (scored["penalty_total"] <= config.MAX_PENALTY).all(), "penalita' oltre il tetto"
sub_cols = [f"sub_{a}" for a in scoring.AXES]
assert all(c in scored.columns for c in sub_cols), "sotto-punteggi mancanti"
fin = scored[scored["sector"] == "Financial Services"]
assert len(fin) and fin["sub_quality"].notna().all(), "binario finanziari rotto"
rows = report.rows_payload(scored)
html = report.build_html(rows, {"generatedAt": "2026-01-01T00:00:00",
    "synthetic": True, "weightsDefault": config.WEIGHTS,
    "collapseThreshold": -0.15})
assert "__DATA_JSON__" not in html and len(html) > 20000
print(f"OK — {len(scored)} titoli, score {scored['score'].min():.1f}..{scored['score'].max():.1f}, HTML {len(html)//1024} kB")
