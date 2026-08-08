# Dislocation Screener

> **Online e automatico:** il progetto include un workflow GitHub Actions
> che rigenera la dashboard ogni notte e la pubblica su GitHub Pages.
> Istruzioni e limiti in [DEPLOY.md](DEPLOY.md).

Cerca società di qualità il cui prezzo è sceso **molto più delle attese sui loro
utili**. L'idea è quella dei casi IBM / Ferrari / Luxottica: un calo violento su
un business che non è peggiorato quanto il prezzo suggerisce.

**Universo: S&P 500 + large cap Europa + large cap Asia** (Giappone, Corea,
Taiwan, Hong Kong/Cina, India, Australia — Samsung, TSMC, SK Hynix inclusi),
circa 900–1.100 titoli, con copertura dedicata ai **semiconduttori** su tutte e
tre le regioni e un filtro "Solo semiconduttori" nella dashboard. Solo fonti
gratuite.

---

## Installazione

```bash
pip install -r requirements.txt
```

## Uso

```bash
python make_preview.py            # anteprima UI con dati finti, 2 secondi
python -m screener.run_screen     # screen vero: 25-50 minuti la prima volta
```

Il primo giro è lento perché scarica i fondamentali di tutto l'universo. Poi la
cache su disco (`.cache/`) rende i giri successivi rapidi: fondamentali ogni 7
giorni, stime/prezzi/notizie ogni giorno. Varianti utili:

```bash
python -m screener.run_screen --quick     # ~5-10 min: prezzi+stime, cache per il resto
python -m screener.run_screen --fast      # fondamentali solo per chi passa il trigger
python -m screener.run_screen --mode or   # trigger permissivo nei mercati calmi
```

Output in `output/`:

| File | Contenuto |
|---|---|
| `latest.html` | **la dashboard** — sempre l'ultima, mettila nei preferiti |
| `screen_DATA.html` | stessa dashboard, archiviata per data |
| `screen_DATA.csv` | i primi 100 con tutte le metriche |
| `raw_DATA.csv` | tutto l'universo dopo i gate, per analisi tue |

## Aggiornamento automatico e "tempo circa reale"

I fondamentali non esistono in tempo reale: cambiano ogni trimestre. Ciò che si
muove ogni giorno sono prezzi, stime e notizie — quindi la scelta corretta è un
**batch giornaliero**, non un flusso di tick. Per posizioni tenute settimane o
mesi non serve altro.

Per avere `latest.html` sempre fresco, pianifica il giro ogni mattina presto
(così prende le chiusure USA e Asia della notte):

**Windows** — Utilità di pianificazione, o da prompt (una riga):

```
schtasks /Create /SC DAILY /ST 07:30 /TN "DislocationScreener" /TR "cmd /c cd /d C:\percorso\dislocation-screener && python -m screener.run_screen --quick"
```

**macOS / Linux** — `crontab -e`:

```
30 7 * * 1-5  cd /percorso/dislocation-screener && python -m screener.run_screen --quick
```

Una volta a settimana lancia il giro pieno (senza `--quick`) per rinfrescare i
fondamentali.

### Come verifichi che i dati siano aggiornati

La dashboard **te lo dice da sola**, in alto a destra: data e ora dell'ultimo
giro, data dei prezzi, età mediana dei fondamentali, copertura delle stime,
stato dei cambi. Il pallino è verde se il giro è recente; se apri un file più
vecchio di ~24 ore compare una fascia ambra, oltre le 72 ore una **fascia rossa**
con il comando da rilanciare. L'anteprima sintetica ha sempre banner rosso
"DATI SINTETICI". Ogni titolo porta inoltre la propria **confidenza**: quanti
campi sono stati davvero popolati per quel nome.

---

## Come funziona

**1. Gate** — esclusioni dure, poche: capitalizzazione > 5 mld USD, controvalore
medio > 5 mln USD/giorno, storia prezzi sufficiente, confidenza dati minima.

**2. Trigger di dislocazione** — il titolo deve essere sceso almeno **1,2 σ**
nell'ultimo mese *e* almeno **10%** dal massimo a 52 settimane. La soglia in
sigma è il punto: −10% su un titolo a volatilità 40% è rumore statistico, su uno
a volatilità 15% è un evento a 2,3 σ. Una soglia percentuale fissa confonde i due.

**3. Score composito** — cinque assi, ognuno costruito su percentili
cross-sezionali calcolati **dentro il settore**, mai su soglie assolute.

| Asse | Peso | Componenti |
|---|---|---|
| Dislocazione | 25% | movimento in σ, excess return vs mediana settore, drawdown, concentrazione del calo |
| Qualità | 25% | ROIC vs settore, trend ROIC, FCF/utile netto, copertura interessi, stabilità margini |
| Valore | 20% | EV/EBITDA, P/E forward, FCF yield — tutti relativi al settore |
| **Repricing gap** | 20% | Δprezzo − Δstime EPS forward, a 30 e 90 giorni |
| Timing | 10% | giorni dal minimo, RSI, volume di capitolazione |

I **finanziari** (banche, assicurazioni) non vengono esclusi: viaggiano su un
binario separato con P/B e ROE al posto di EV/EBITDA e net debt — è proprio lì
che capitano i panici più irrazionali.

**4. Penalità** fino a −30 punti: leva oltre il limite di settore, copertura
interessi debole, FCF negativo, ricavi o ROIC in calo, short interest alto,
stime in crollo, dati incompleti.

I pesi si modificano **dal vivo nella dashboard**: i sotto-punteggi sono salvati
separatamente, quindi il ranking si ricalcola nel browser senza rilanciare nulla.

### Il Repricing Gap

```
gap = Δ prezzo (1 mese) − Δ stima EPS FY+1 (30 giorni)
```

È la metrica che fa il lavoro vero.

- **gap molto negativo** — il prezzo è crollato, le stime quasi no. Candidato mispricing.
- **gap vicino a zero** — prezzo e stime sono scesi insieme. Il mercato ha
  riprezzato correttamente. Nessuna occasione.
- **stime giù oltre il 15% in 90 giorni** — l'asse viene compresso al 40% e
  scatta una penalità. Qui non c'è mispricing, c'è *post-earnings drift*:
  storicamente i cali su notizie fondamentali continuano per 60+ giorni.

Questa distinzione è tutto il progetto. Il resto è contorno.

### Il "perché" del calo

Cliccando una riga si apre il dettaglio con le **ultime notizie** del titolo
(fonte Yahoo, gratis, scaricate per i primi 120 candidati) e un link diretto
"Perché è sceso → notizie" che apre la ricerca stampa sul nome. Lo screener non
interpreta le notizie: te le mette davanti. La lettura resta compito tuo, ed è
il passo che nessuna dashboard può eliminare.

---

## Cosa NON fa

Onestà su cosa il budget zero ti costa davvero:

- **Le stime di consenso sono la parte fragile.** Yahoo le espone via
  `eps_trend`: copertura buona sugli US e sugli ADR, discreta sulle large cap
  europee, **irregolare sui listini locali asiatici** (per questo dove esiste un
  ADR liquido — TSMC, Alibaba, ASML — lo screener usa quello). Controlla sempre
  la confidenza del singolo titolo.
- **Nessun segnale dal credito.** CDS e spread obbligazionari sarebbero il
  controllo incrociato migliore. Non esistono gratis.
- **Niente insider buying.** Per gli US si può aggiungere via SEC EDGAR Form 4;
  per Europa e Asia la frammentazione regolamentare lo rende poco pratico.
- **Valute:** i multipli restano in valuta locale (sono rapporti, è corretto);
  capitalizzazioni e controvalori sono convertiti in USD con cambi scaricati a
  ogni giro (se il download fallisce, tassi statici di riserva e la dashboard
  segnala "FX di riserva").
- **Nessun backtest.** Non sai se questo score funziona. Vedi sotto.

## Validazione: falla prima di usarlo

1. Prendi le date dei crolli di IBM, Ferrari e Luxottica (e, se vuoi, di un caso
   semis tipo il de-rating 2022 di TSMC/Samsung).
2. Ricostruisci prezzi a quella data (`yf.download` con `start`/`end`); le stime
   storiche non sono recuperabili gratis, quindi il Repricing Gap va
   approssimato con le revisioni pubblicate più vicine.
3. Guarda dove sarebbero finiti nel ranking. Se lo screen non li pesca, è lo
   score da correggere — non i casi.

Quando il mercato è calmo il trigger può restituire pochissimi titoli. È il
comportamento corretto: non ci sono dislocazioni. Se vuoi comunque vedere
qualcosa: `--mode or`, oppure abbassa `min_sigma_move_1m` in `config.py`.

## Personalizzazione

Tutto in `screener/config.py` (pesi, trigger, esclusioni, limiti di leva,
penalità). Universo in `screener/universe.py`: `EUROPE_SEED`, `ASIA_SEED`,
`SEMICONDUCTORS`, `PREFER_ADR` — aggiungi o togli ticker liberamente.

## Avvertenza

Strumento **didattico**: produce candidati da analizzare a mano, non
raccomandazioni. Uno score alto significa soltanto che un titolo assomiglia a un
profilo statistico, calcolato su dati che possono essere incompleti, in ritardo
o sbagliati. Non stima rendimenti attesi e non conosce il motivo per cui il
prezzo è sceso. La strategia "comprare qualità crollata" perde denaro in due
modi ricorrenti: prendere il coltello che cade, e scambiare un declino
strutturale per una dislocazione temporanea. Nessun filtro qui dentro protegge
da nessuno dei due. Ogni operazione avviene fuori da qui, sul tuo broker, con
capitale che puoi permetterti di perdere e attenzione alla correlazione: se
trenta candidati sono tutti semiconduttori, hai una scommessa sola, non trenta.
