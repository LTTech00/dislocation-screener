"""
Assembla la cartella `site/` da pubblicare, e prima di farlo decide se la run
merita di essere pubblicata.

  python -m screener.publish --site site --keep 60

Il guasto peggiore di un sistema automatico non e' la run che fallisce: e'
quella che riesce a meta'. Yahoo restituisce 200 con corpo vuoto per meta'
universo, la pipeline non solleva eccezioni, il sito si aggiorna con 12
titoli invece di 200 e la pagina dice "aggiornato adesso". Il numero e'
falso ma sembra fresco, ed e' peggio di una pagina vecchia dichiarata vecchia.

Per questo la pubblicazione e' condizionata a soglie di copertura. Se non
sono rispettate, il publish esce con codice != 0, il deploy non parte e
resta online l'ultima versione buona — che invecchia in modo visibile
grazie al banner di freschezza gia' presente nel report.
"""
from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timedelta
from pathlib import Path

OUT = Path("output")

# Soglie minime perche' una run sia considerata pubblicabile.
GATES = {
    "min_universe": 250,      # titoli con prezzi validi
    "min_gated": 80,          # titoli sopravvissuti alle esclusioni dure
    "min_est_coverage": 25.0, # % di candidati con stime di consenso
    "max_age_hours": 6,       # il report deve essere di questa run
}


def load_meta(report: Path) -> dict:
    """Rilegge il blocco JSON incorporato nel report."""
    html = report.read_text(encoding="utf-8")
    start = html.find('<script id="data" type="application/json">')
    if start == -1:
        raise SystemExit("Report senza blocco dati: formato inatteso.")
    start = html.index(">", start) + 1
    end = html.index("</script>", start)
    return json.loads(html[start:end])["meta"]


def check(meta: dict, strict: bool = True) -> list[str]:
    """Ritorna la lista dei problemi. Vuota = pubblicabile."""
    problems = []

    if meta.get("synthetic"):
        problems.append("report generato con dati sintetici")

    uni = meta.get("universeCount") or 0
    if uni < GATES["min_universe"]:
        problems.append(
            f"universo troppo piccolo: {uni} < {GATES['min_universe']} "
            "(probabile rate limiting: Yahoo ha risposto vuoto)")

    gated = meta.get("gatedCount") or 0
    if gated < GATES["min_gated"]:
        problems.append(f"pochi titoli dopo le esclusioni: {gated} < {GATES['min_gated']}")

    cov = meta.get("estCoveragePct")
    if cov is not None and cov < GATES["min_est_coverage"]:
        problems.append(
            f"copertura stime {cov:.0f}% < {GATES['min_est_coverage']:.0f}% — "
            "il Repricing Gap sarebbe neutro quasi ovunque")

    gen = meta.get("generatedAt")
    if gen:
        age = datetime.now() - datetime.fromisoformat(gen)
        if age > timedelta(hours=GATES["max_age_hours"]):
            problems.append(f"report vecchio di {age.total_seconds()/3600:.0f}h: "
                            "non appartiene a questa run")

    # Un universo che passa i gate ma con zero candidati NON e' un errore:
    # significa mercato calmo, ed e' un'informazione legittima da pubblicare.
    if not strict:
        return [p for p in problems if "sintetici" in p]
    return problems


def build_site(site: Path, keep: int) -> dict:
    reports = sorted(OUT.glob("screen_*.html"))
    if not reports:
        raise SystemExit("Nessun report in output/. Esegui prima run_screen.")
    latest = reports[-1]
    meta = load_meta(latest)

    site.mkdir(parents=True, exist_ok=True)
    archive = site / "archive"
    archive.mkdir(exist_ok=True)

    # index.html = la copia sempre corrente, URL stabile
    shutil.copyfile(latest, site / "index.html")
    shutil.copyfile(latest, archive / latest.name)

    for csv in OUT.glob("screen_*.csv"):
        shutil.copyfile(csv, archive / csv.name)

    # potatura: l'archivio non deve crescere all'infinito
    for group in ("screen_*.html", "screen_*.csv"):
        files = sorted(archive.glob(group))
        for old in files[:-keep]:
            old.unlink()

    history = [
        {"name": f.name, "date": f.stem.replace("screen_", "")}
        for f in sorted(archive.glob("screen_*.html"), reverse=True)
    ]
    (site / "history.json").write_text(
        json.dumps(history, indent=1), encoding="utf-8")

    # endpoint minimo per monitoraggio esterno (uptime robot, cron-ping, ecc.)
    (site / "status.json").write_text(json.dumps({
        "generatedAt": meta.get("generatedAt"),
        "universeCount": meta.get("universeCount"),
        "gatedCount": meta.get("gatedCount"),
        "triggeredCount": meta.get("triggeredCount"),
        "estCoveragePct": meta.get("estCoveragePct"),
        "fxFresh": meta.get("fxFresh"),
    }, indent=1), encoding="utf-8")

    (site / ".nojekyll").touch()   # GitHub Pages: non processare con Jekyll
    return meta


def main() -> None:
    ap = argparse.ArgumentParser(description="Prepara la cartella da pubblicare")
    ap.add_argument("--site", default="site", help="cartella di destinazione")
    ap.add_argument("--keep", type=int, default=60, help="report da conservare")
    ap.add_argument("--allow-empty", action="store_true",
                    help="pubblica anche con zero candidati (mercato calmo)")
    ap.add_argument("--force", action="store_true",
                    help="ignora i controlli di copertura")
    args = ap.parse_args()

    site = Path(args.site)
    meta = build_site(site, args.keep)
    problems = check(meta, strict=not args.force)

    print(f"universo {meta.get('universeCount')} · "
          f"dopo esclusioni {meta.get('gatedCount')} · "
          f"candidati {meta.get('triggeredCount')} · "
          f"stime {meta.get('estCoveragePct') or 0:.0f}%")

    if problems:
        print("\nPUBBLICAZIONE BLOCCATA:")
        for p in problems:
            print(f"  - {p}")
        print("\nResta online l'ultima versione buona, che invecchiando "
              "mostrera' da sola il banner di dati stantii.")
        raise SystemExit(1)

    if not meta.get("triggeredCount") and not args.allow_empty:
        print("\nZero candidati oltre il trigger. Non e' un errore: e' un "
              "mercato calmo. Usa --allow-empty per pubblicare comunque.")
        raise SystemExit(2)

    print(f"\nOK — pronto in {site}/ (index.html + archive/ + status.json)")


if __name__ == "__main__":
    main()
